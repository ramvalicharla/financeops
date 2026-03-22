from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, get_redis
from financeops.config import limiter, settings
from financeops.core.exceptions import AuthenticationError
from financeops.core.security import decode_token, verify_password
from financeops.db.models.tenants import TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.services.audit_service import log_action
from financeops.services.auth_service import (
    create_mfa_challenge,
    login,
    logout,
    refresh_tokens,
    setup_totp,
    verify_mfa_challenge,
    verify_totp_setup,
)
from financeops.services.credit_service import add_credits
from financeops.services.tenant_service import create_default_workspace, create_tenant
from financeops.services.user_service import create_user, get_user_by_email

log = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_name: str
    tenant_type: TenantType
    country: str


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
    totp_code: str


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
    await session.flush()
    return {
        "user_id": str(user.id),
        "tenant_id": str(tenant.id),
        "mfa_setup_required": True,
    }


@router.post("/mfa/setup")
async def mfa_setup(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    POST /api/v1/auth/mfa/setup
    Generate and store TOTP secret. Returns secret + QR code URL.
    """
    result = await setup_totp(user, session)
    await session.flush()
    return {
        "totp_secret": result["totp_secret"],
        "qr_code_url": result["qr_code_url"],
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
    tenant = await get_tenant(session, user.tenant_id)
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
            "tenant_type": tenant.tenant_type.value,
            "country": tenant.country,
            "timezone": tenant.timezone,
            "status": tenant.status.value,
        },
    }
