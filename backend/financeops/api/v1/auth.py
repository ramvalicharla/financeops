from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from financeops.api.deps import get_async_session, get_current_user, get_redis
from financeops.config import limiter, settings
from financeops.core.exceptions import AuthenticationError
from financeops.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_field,
    hash_password,
    verify_password,
    verify_totp,
)
from financeops.db.models.auth_tokens import MfaRecoveryCode, PasswordResetToken
from financeops.db.models.tenants import TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.notifications.channels.email_channel import send_direct
from financeops.modules.notifications.templates.emails import welcome_email
from financeops.services.audit_service import log_action
from financeops.services.auth_service import (
    build_billing_token_claims,
    create_mfa_challenge,
    login,
    logout,
    refresh_tokens,
    revoke_all_sessions,
    setup_totp,
    verify_mfa_challenge,
)
from financeops.services.credit_service import add_credits
from financeops.services.tenant_service import create_default_workspace, create_tenant
from financeops.services.user_service import create_user, get_user_by_email

log = logging.getLogger(__name__)
router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_name: str
    tenant_type: TenantType
    country: str
    phone: str | None = None
    terms_accepted: bool | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MfaVerifyRequest(BaseModel):
    mfa_challenge_token: str
    totp_code: str | None = None
    recovery_code: str | None = None


class MFAVerifySetupRequest(BaseModel):
    secret: str | None = None
    code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    terms_accepted: bool = True


def generate_mfa_setup_token(user: IamUser) -> str:
    return create_access_token(
        user.id,
        user.tenant_id,
        user.role.value,
        additional_claims={"scope": "mfa_setup_only"},
        expires_delta=timedelta(minutes=15),
    )


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [
        f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        for _ in range(count)
    ]


async def get_current_user_or_setup_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> IamUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    payload = decode_token(credentials.credentials)
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id_raw = payload.get("sub")
    tenant_id_raw = payload.get("tenant_id")
    if not user_id_raw or not tenant_id_raw:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    try:
        user_id = uuid.UUID(str(user_id_raw))
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc
    await set_tenant_context(session, tenant_id)
    user = (
        await session.execute(
            select(IamUser).where(IamUser.id == user_id, IamUser.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    if payload.get("scope") == "mfa_setup_only":
        return user
    if user.force_mfa_setup and not user.mfa_enabled:
        return user
    return user


async def _set_refresh_tenant_context(
    session: AsyncSession,
    refresh_token: str,
) -> None:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise AuthenticationError("Token missing tenant_id")
    await set_tenant_context(session, tenant_id)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    POST /api/v1/auth/register
    Creates tenant + user + initial credit balance.
    Returns user_id, tenant_id, mfa_setup_required=True.
    """
    if not body.terms_accepted:
        raise HTTPException(
            status_code=422,
            detail="Terms of service must be accepted to register.",
        )

    tenant = await create_tenant(
        session,
        display_name=body.tenant_name,
        tenant_type=body.tenant_type,
        country=body.country,
    )
    await set_tenant_context(session, tenant.id)
    await create_default_workspace(session, tenant.id)

    user = await create_user(
        session,
        tenant_id=tenant.id,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=UserRole.finance_leader,
    )

    # Seed initial trial credits
    from decimal import Decimal
    await add_credits(
        session,
        tenant_id=tenant.id,
        amount=Decimal("100"),
        reason="trial_signup",
        user_id=user.id,
    )

    await log_action(
        session,
        tenant_id=tenant.id,
        user_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=str(user.id),
        resource_name=user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    user.terms_accepted_at = datetime.utcnow()
    user.terms_version_accepted = settings.CURRENT_TERMS_VERSION
    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    subject, html = welcome_email(
        full_name=user.full_name,
        company_name=tenant.display_name,
        dashboard_url=f"{frontend_base}/dashboard",
        unsubscribe_url=f"{frontend_base}/settings/privacy",
    )
    await send_direct(
        to=user.email,
        subject=subject,
        html_body=html,
        text_body="Welcome to FinanceOps. Your account is ready.",
    )
    await session.flush()
    await session.commit()
    setup_token = generate_mfa_setup_token(user)
    return {
        "user_id": str(user.id),
        "tenant_id": str(tenant.id),
        "status": "requires_mfa_setup",
        "setup_token": setup_token,
        "mfa_setup_required": True,
    }


@router.post("/mfa/setup")
async def mfa_setup(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user_or_setup_token),
) -> dict:
    """
    POST /api/v1/auth/mfa/setup
    Generate and store TOTP secret. Returns secret + QR code URL.
    """
    result = await setup_totp(user, session)
    await session.flush()
    return {
        "secret": result["totp_secret"],
        "qr_url": result["qr_code_url"],
    }


@router.post("/mfa/verify-setup")
async def verify_mfa_setup(
    body: MFAVerifySetupRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user_or_setup_token),
) -> dict:
    if not user.totp_secret_encrypted:
        raise AuthenticationError("MFA not initialized for user")
    if body.secret:
        log.warning(
            "Client supplied secret in /api/v1/auth/mfa/verify-setup payload; ignoring user_id=%s",
            user.id,
        )
    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user.mfa_enabled = True
    user.force_mfa_setup = False

    plain_codes = generate_recovery_codes(8)
    for code in plain_codes:
        session.add(
            MfaRecoveryCode(
                user_id=user.id,
                code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            )
        )

    await session.flush()

    billing_claims = await build_billing_token_claims(session, tenant_id=user.tenant_id)
    access_token = create_access_token(
        user.id,
        user.tenant_id,
        user.role.value,
        additional_claims=billing_claims,
    )
    refresh_token = create_refresh_token(user.id, user.tenant_id)
    return {
        "status": "mfa_enabled",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "recovery_codes": plain_codes,
    }


@limiter.limit(settings.AUTH_MFA_RATE_LIMIT)
@router.post("/mfa/verify")
async def mfa_verify(
    request: Request,
    body: MfaVerifyRequest,
    session: AsyncSession = Depends(get_async_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    POST /api/v1/auth/mfa/verify
    Verify MFA challenge token + TOTP and issue token pair.
    """
    user, tokens = await verify_mfa_challenge(
        session,
        redis_client,
        mfa_challenge_token=body.mfa_challenge_token,
        totp_code=body.totp_code,
        recovery_code=body.recovery_code,
        ip_address=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent"),
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user.login.mfa_verified",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return tokens


@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)
@router.post("/login")
async def user_login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    POST /api/v1/auth/login
    Authenticate user, verify MFA if enabled, return token pair.
    """
    user = await get_user_by_email(session, body.email)
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.hashed_password)
    ):
        raise AuthenticationError("Invalid email or password")
    await set_tenant_context(session, user.tenant_id)

    if user.force_mfa_setup and not user.mfa_enabled:
        setup_token = generate_mfa_setup_token(user)
        return {
            "status": "requires_mfa_setup",
            "requires_mfa_setup": True,
            "setup_token": setup_token,
        }
    if user.mfa_enabled:
        challenge_token = await create_mfa_challenge(redis_client, user=user)
        return {
            "requires_mfa": True,
            "mfa_challenge_token": challenge_token,
        }

    tokens = await login(
        session,
        user=user,
        totp_code=body.totp_code,
        ip_address=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent"),
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return tokens


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    user = await get_user_by_email(session, body.email)
    if user is not None:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        await session.flush()
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    record = (
        await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .where(PasswordResetToken.used_at.is_(None))
        )
    ).scalar_one_or_none()
    if record is None or record.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = await session.get(IamUser, record.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.hashed_password = hash_password(body.new_password)
    record.used_at = datetime.now(UTC)
    await session.flush()
    return {"message": "Password reset successful. Please sign in."}


@router.post("/accept-invite")
async def accept_invite(
    body: AcceptInviteRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="Terms of Service must be accepted")

    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    user = (
        await session.execute(
            select(IamUser)
            .where(IamUser.invite_token_hash == token_hash)
            .where(IamUser.is_active.is_(False))
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid invitation link")
    if user.invite_expires_at and user.invite_expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired. Request a new one from your administrator.",
        )

    user.hashed_password = hash_password(body.password)
    user.is_active = True
    user.invite_token_hash = None
    user.invite_accepted_at = datetime.now(UTC)
    user.terms_accepted_at = datetime.utcnow()
    user.terms_version_accepted = settings.CURRENT_TERMS_VERSION
    await session.flush()
    return {"message": "Account activated. Please sign in."}


@limiter.limit(settings.AUTH_TOKEN_RATE_LIMIT)
@router.post("/refresh")
async def token_refresh(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    POST /api/v1/auth/refresh
    Rotate refresh token — invalidate old, issue new pair.
    """
    await _set_refresh_tenant_context(session, body.refresh_token)
    tokens = await refresh_tokens(session, body.refresh_token)
    await session.flush()
    return tokens


@router.post("/logout")
async def user_logout(
    body: LogoutRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    POST /api/v1/auth/logout
    Revoke current session in DB.
    """
    await _set_refresh_tenant_context(session, body.refresh_token)
    await logout(session, body.refresh_token)
    await session.flush()
    return {"logged_out": True}


@limiter.limit(settings.AUTH_TOKEN_RATE_LIMIT)
@router.post("/sessions/revoke-all")
async def revoke_all_my_sessions(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    Revoke all active refresh sessions for current user.
    Access tokens remain valid until expiry; refresh is blocked immediately.
    """
    revoked_count = await revoke_all_sessions(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user.sessions.revoke_all",
        resource_type="iam_session",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return {"revoked_sessions": revoked_count}


@router.get("/me")
async def get_me(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    GET /api/v1/auth/me
    Returns current user profile + tenant info.
    """
    from financeops.services.tenant_service import get_tenant
    from financeops.db.models.payment import BillingPlan, TenantSubscription

    tenant = await get_tenant(session, user.tenant_id)
    subscription = (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == user.tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    plan_payload: dict | None = None
    if subscription is not None:
        plan = (
            await session.execute(
                select(BillingPlan).where(
                    BillingPlan.tenant_id == user.tenant_id,
                    BillingPlan.id == subscription.plan_id,
                )
            )
        ).scalar_one_or_none()
        if plan is not None:
            plan_payload = {
                "id": str(plan.id),
                "name": plan.name,
                "plan_tier": plan.plan_tier,
                "pricing_type": plan.pricing_type,
                "price": str(plan.price) if plan.price is not None else None,
                "currency": plan.currency,
            }
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "mfa_enabled": user.mfa_enabled,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "tenant": {
            "tenant_id": str(tenant.id),
            "display_name": tenant.display_name,
            "slug": tenant.slug,
            "tenant_type": tenant.tenant_type.value,
            "country": tenant.country,
            "timezone": tenant.timezone,
            "status": tenant.status.value,
            "org_setup_complete": tenant.org_setup_complete,
            "org_setup_step": tenant.org_setup_step,
        },
        "billing": None
        if subscription is None
        else {
            "subscription_id": str(subscription.id),
            "plan_id": str(subscription.plan_id),
            "status": subscription.status,
            "plan": plan_payload,
        },
    }
