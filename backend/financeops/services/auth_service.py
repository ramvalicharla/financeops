from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.exceptions import AuthenticationError, AuthorizationError
from financeops.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_field,
    encrypt_field,
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
)
from financeops.db.models.users import IamSession, IamUser
from financeops.db.models.auth_tokens import MfaRecoveryCode
from financeops.db.models.payment import BillingPlan, TenantSubscription
from financeops.observability.beta_monitoring import record_auth_event
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)

_REFRESH_TOKEN_EXPIRE_DAYS = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for safe storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def login(
    session: AsyncSession,
    *,
    user: IamUser,
    totp_code: str | None,
    ip_address: str | None = None,
    device_info: str | None = None,
) -> dict:
    """
    Complete login flow:
    1. Verify MFA if enabled
    2. Issue access + refresh tokens
    3. Create IamSession record
    Returns: {"access_token": ..., "refresh_token": ..., "token_type": "bearer"}
    """
    if user.mfa_enabled:
        if not totp_code:
            record_auth_event(
                event="auth_login_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="missing_totp_code",
            )
            raise AuthorizationError("TOTP code required for MFA-enabled accounts")
        encrypted_secret = user.totp_secret_encrypted
        if not encrypted_secret:
            record_auth_event(
                event="auth_login_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="mfa_secret_missing",
            )
            raise AuthenticationError("MFA is enabled but no secret configured")
        secret = decrypt_field(encrypted_secret)
        if not verify_totp(secret, totp_code):
            record_auth_event(
                event="auth_login_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="invalid_totp_code",
            )
            raise AuthenticationError("Invalid TOTP code")

    return await _issue_session_tokens(
        session,
        user=user,
        ip_address=ip_address,
        device_info=device_info,
    )


async def _issue_session_tokens(
    session: AsyncSession,
    *,
    user: IamUser,
    ip_address: str | None = None,
    device_info: str | None = None,
) -> dict:
    token_claims = await build_billing_token_claims(session, tenant_id=user.tenant_id)
    access_token = create_access_token(
        user.id,
        user.tenant_id,
        user.role.value,
        additional_claims=token_claims,
    )
    refresh_token = create_refresh_token(user.id, user.tenant_id)
    refresh_token_hash = _hash_token(refresh_token)

    await AuditWriter.insert_record(
        session,
        record=IamSession(
            user_id=user.id,
            tenant_id=user.tenant_id,
            refresh_token_hash=refresh_token_hash,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=datetime.now(UTC)
            + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
        ),
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.session.created",
            resource_type="iam_session",
            resource_name=user.email,
            new_value={"ip_address": ip_address, "device_info": device_info},
        ),
    )
    user.last_login_at = datetime.now(UTC)
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.user.last_login.updated",
            resource_type="user",
            resource_id=str(user.id),
            resource_name=user.email,
            new_value={"last_login_at": user.last_login_at.isoformat()},
        ),
    )
    log.info(
        "Login success: user=%s tenant=%s", str(user.id)[:8], str(user.tenant_id)[:8]
    )
    record_auth_event(
        event="auth_login_succeeded",
        outcome="success",
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def create_mfa_challenge(
    redis_client: aioredis.Redis,
    *,
    user: IamUser,
    ttl_seconds: int = 90,
) -> str:
    """
    Issue a short-lived, single-use MFA challenge token stored in Redis.
    """
    token = secrets.token_urlsafe(32)
    key = f"mfa_challenge:{token}"
    payload = json.dumps(
        {
            "user_id": str(user.id),
            "tenant_id": str(user.tenant_id),
        }
    )
    await redis_client.setex(key, ttl_seconds, payload)
    return token


async def create_mfa_setup_token(
    redis_client: aioredis.Redis,
    *,
    user: IamUser,
    ttl_seconds: int = 3600,
) -> str:
    """
    Issue a setup token used when force_mfa_setup is enabled.
    """
    token = secrets.token_urlsafe(32)
    key = f"mfa_setup:{token}"
    payload = json.dumps(
        {
            "user_id": str(user.id),
            "tenant_id": str(user.tenant_id),
        }
    )
    await redis_client.setex(key, ttl_seconds, payload)
    return token


async def verify_mfa_challenge(
    session: AsyncSession,
    redis_client: aioredis.Redis,
    *,
    mfa_challenge_token: str,
    totp_code: str | None = None,
    recovery_code: str | None = None,
    ip_address: str | None = None,
    device_info: str | None = None,
) -> tuple[IamUser, dict]:
    """
    Validate MFA challenge token + TOTP and issue auth tokens.
    """
    key = f"mfa_challenge:{mfa_challenge_token}"
    raw_payload = await redis_client.get(key)
    if not raw_payload:
        log.info("MFA verify rejected: expired_challenge")
        record_auth_event(
            event="auth_mfa_verify_failed",
            outcome="failure",
            failure_type="expired_challenge",
        )
        raise AuthenticationError("MFA challenge expired")

    try:
        challenge_payload = json.loads(raw_payload)
        user_id = challenge_payload["user_id"]
        tenant_id = challenge_payload["tenant_id"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        log.warning("MFA verify rejected: invalid_challenge_payload")
        record_auth_event(
            event="auth_mfa_verify_failed",
            outcome="failure",
            failure_type="invalid_challenge_payload",
        )
        raise AuthenticationError("Invalid MFA challenge payload") from exc

    user_result = await session.execute(
        select(IamUser).where(
            IamUser.id == user_id,
            IamUser.tenant_id == tenant_id,
            IamUser.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        log.info("MFA verify rejected: user_not_found_for_challenge")
        record_auth_event(
            event="auth_mfa_verify_failed",
            outcome="failure",
            failure_type="user_not_found_for_challenge",
        )
        raise AuthenticationError("User not found")
    if not user.mfa_enabled or not user.totp_secret_encrypted:
        log.info("MFA verify rejected: mfa_not_configured")
        record_auth_event(
            event="auth_mfa_verify_failed",
            outcome="failure",
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            failure_type="mfa_not_configured",
        )
        raise AuthenticationError("MFA is not configured for this account")

    secret = decrypt_field(user.totp_secret_encrypted)
    log.debug(
        "MFA challenge verify attempt user=%s tenant=%s method=%s",
        str(user.id),
        str(user.tenant_id),
        "recovery_code" if recovery_code else "totp_code",
    )
    if recovery_code:
        recovery_hash = hashlib.sha256(recovery_code.strip().upper().encode("utf-8")).hexdigest()
        recovery_row = (
            await session.execute(
                select(MfaRecoveryCode)
                .where(MfaRecoveryCode.user_id == user.id)
                .where(MfaRecoveryCode.code_hash == recovery_hash)
                .where(MfaRecoveryCode.used_at.is_(None))
            )
        ).scalar_one_or_none()
        if recovery_row is None:
            log.info("MFA verify rejected: invalid_recovery_code user=%s", str(user.id))
            record_auth_event(
                event="auth_mfa_verify_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="invalid_recovery_code",
            )
            raise AuthenticationError("Invalid recovery code")
        recovery_row.used_at = datetime.now(UTC)
    else:
        if not totp_code:
            log.info("MFA verify rejected: missing_totp_code user=%s", str(user.id))
            record_auth_event(
                event="auth_mfa_verify_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="missing_totp_code",
            )
            raise AuthenticationError("TOTP code required")
        if not verify_totp(secret, totp_code):
            log.info("MFA verify rejected: invalid_totp_code user=%s", str(user.id))
            record_auth_event(
                event="auth_mfa_verify_failed",
                outcome="failure",
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                failure_type="invalid_totp_code",
            )
            raise AuthenticationError("Invalid TOTP code")

    await redis_client.delete(key)
    tokens = await _issue_session_tokens(
        session,
        user=user,
        ip_address=ip_address,
        device_info=device_info,
    )
    record_auth_event(
        event="auth_mfa_verify_succeeded",
        outcome="success",
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    return user, tokens


async def refresh_tokens(
    session: AsyncSession,
    refresh_token: str,
) -> dict:
    """
    Rotate refresh token: invalidate old, issue new pair.
    Returns new access_token + refresh_token.
    """
    token_hash = _hash_token(refresh_token)
    result = await session.execute(
        select(IamSession).where(
            IamSession.refresh_token_hash == token_hash,
            IamSession.revoked_at.is_(None),
        )
    )
    db_session = result.scalar_one_or_none()
    if db_session is None:
        record_auth_event(
            event="auth_token_refresh_failed",
            outcome="failure",
            failure_type="invalid_or_revoked_refresh_token",
        )
        raise AuthenticationError("Invalid or revoked refresh token")
    if db_session.expires_at < datetime.now(UTC):
        record_auth_event(
            event="auth_token_refresh_failed",
            outcome="failure",
            user_id=db_session.user_id,
            tenant_id=db_session.tenant_id,
            failure_type="refresh_token_expired",
        )
        raise AuthenticationError("Refresh token has expired")

    # Revoke old session
    old_session_state = {"revoked_at": None}
    db_session.revoked_at = datetime.now(UTC)
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=db_session.tenant_id,
            user_id=db_session.user_id,
            action="auth.session.revoked_for_rotation",
            resource_type="iam_session",
            resource_id=str(db_session.id),
            old_value=old_session_state,
            new_value={"revoked_at": db_session.revoked_at.isoformat()},
        ),
    )

    # Load user
    user_result = await session.execute(
        select(IamUser).where(IamUser.id == db_session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        record_auth_event(
            event="auth_token_refresh_failed",
            outcome="failure",
            user_id=db_session.user_id,
            tenant_id=db_session.tenant_id,
            failure_type="refresh_user_missing_or_inactive",
        )
        raise AuthenticationError("User not found or deactivated")

    token_claims = await build_billing_token_claims(session, tenant_id=user.tenant_id)
    new_access = create_access_token(
        user.id,
        user.tenant_id,
        user.role.value,
        additional_claims=token_claims,
    )
    new_refresh = create_refresh_token(user.id, user.tenant_id)
    new_hash = _hash_token(new_refresh)

    await AuditWriter.insert_record(
        session,
        record=IamSession(
            user_id=user.id,
            tenant_id=user.tenant_id,
            refresh_token_hash=new_hash,
            device_info=db_session.device_info,
            ip_address=db_session.ip_address,
            expires_at=datetime.now(UTC)
            + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
        ),
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.session.rotated",
            resource_type="iam_session",
            resource_name=user.email,
            new_value={"previous_session_id": str(db_session.id)},
        ),
    )
    record_auth_event(
        event="auth_token_refreshed",
        outcome="success",
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


async def build_billing_token_claims(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    subscription = (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if subscription is None:
        return {}

    claims: dict[str, str] = {
        "subscription_id": str(subscription.id),
        "plan_id": str(subscription.plan_id),
        "subscription_status": subscription.status,
    }
    plan = (
        await session.execute(
            select(BillingPlan).where(
                BillingPlan.tenant_id == tenant_id,
                BillingPlan.id == subscription.plan_id,
            )
        )
    ).scalar_one_or_none()
    if plan is not None:
        claims["plan_tier"] = plan.plan_tier
    return claims


async def logout(session: AsyncSession, refresh_token: str) -> None:
    """Revoke the session associated with the given refresh token."""
    token_hash = _hash_token(refresh_token)
    result = await session.execute(
        select(IamSession).where(IamSession.refresh_token_hash == token_hash)
    )
    db_session = result.scalar_one_or_none()
    if db_session and db_session.revoked_at is None:
        old_state = {"revoked_at": None}
        db_session.revoked_at = datetime.now(UTC)
        await AuditWriter.flush_with_audit(
            session,
            audit=AuditEvent(
                tenant_id=db_session.tenant_id,
                user_id=db_session.user_id,
                action="auth.session.revoked",
                resource_type="iam_session",
                resource_id=str(db_session.id),
                old_value=old_state,
                new_value={"revoked_at": db_session.revoked_at.isoformat()},
            ),
        )


async def revoke_all_sessions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """
    Revoke every active refresh session for a user.
    """
    now = datetime.now(UTC)
    result = await session.execute(
        update(IamSession)
        .where(
            IamSession.tenant_id == tenant_id,
            IamSession.user_id == user_id,
            IamSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    revoked_count = int(result.rowcount or 0)
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="auth.session.revoked_all",
            resource_type="iam_session",
            resource_name=f"revoked_count={revoked_count}",
            new_value={"revoked_count": revoked_count, "revoked_at": now.isoformat()},
        ),
    )
    return revoked_count


async def setup_totp(user: IamUser, session: AsyncSession) -> dict:
    """
    Generate a new TOTP secret, encrypt and store it, return the setup info.
    MFA is NOT activated until verify_totp_setup() is called.
    """
    old_state = {"mfa_enabled": user.mfa_enabled}
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_field(secret)
    user.mfa_enabled = False  # Not active until verified
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.totp.setup",
            resource_type="user",
            resource_id=str(user.id),
            resource_name=user.email,
            old_value=old_state,
            new_value={"mfa_enabled": user.mfa_enabled},
        ),
    )
    uri = get_totp_uri(secret, user.email)
    log.debug(
        "MFA setup generated user=%s tenant=%s issuer=FinanceOps account=%s",
        str(user.id),
        str(user.tenant_id),
        user.email.strip().lower(),
    )
    return {
        "totp_secret": secret,
        "qr_code_url": uri,
    }


async def verify_totp_setup(user: IamUser, code: str, session: AsyncSession) -> bool:
    """
    Verify the TOTP code against stored secret and activate MFA.
    Raises AuthenticationError if code is wrong.
    """
    if not user.totp_secret_encrypted:
        raise AuthenticationError("TOTP setup not initiated")
    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, code):
        raise AuthenticationError("Invalid TOTP code — please try again")
    old_state = {"mfa_enabled": user.mfa_enabled}
    user.mfa_enabled = True
    user.force_mfa_setup = False
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.totp.verified",
            resource_type="user",
            resource_id=str(user.id),
            resource_name=user.email,
            old_value=old_state,
            new_value={
                "mfa_enabled": user.mfa_enabled,
                "force_mfa_setup": user.force_mfa_setup,
            },
        ),
    )
    return True

