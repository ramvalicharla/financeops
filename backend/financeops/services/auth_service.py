from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError, AuthorizationError
from financeops.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_field,
    encrypt_field,
    generate_totp_secret,
    get_totp_uri,
    verify_password,
    verify_totp,
)
from financeops.db.models.users import IamSession, IamUser
from financeops.config import settings

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
            raise AuthorizationError("TOTP code required for MFA-enabled accounts")
        encrypted_secret = user.totp_secret_encrypted
        if not encrypted_secret:
            raise AuthenticationError("MFA is enabled but no secret configured")
        secret = decrypt_field(encrypted_secret)
        if not verify_totp(secret, totp_code):
            raise AuthenticationError("Invalid TOTP code")

    access_token = create_access_token(user.id, user.tenant_id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.tenant_id)
    refresh_token_hash = _hash_token(refresh_token)

    db_session = IamSession(
        user_id=user.id,
        tenant_id=user.tenant_id,
        refresh_token_hash=refresh_token_hash,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=datetime.now(timezone.utc) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_session)
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    log.info("Login success: user=%s tenant=%s", str(user.id)[:8], str(user.tenant_id)[:8])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


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
        raise AuthenticationError("Invalid or revoked refresh token")
    if db_session.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired")

    # Revoke old session
    db_session.revoked_at = datetime.now(timezone.utc)

    # Load user
    user_result = await session.execute(
        select(IamUser).where(IamUser.id == db_session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or deactivated")

    new_access = create_access_token(user.id, user.tenant_id, user.role.value)
    new_refresh = create_refresh_token(user.id, user.tenant_id)
    new_hash = _hash_token(new_refresh)

    new_session = IamSession(
        user_id=user.id,
        tenant_id=user.tenant_id,
        refresh_token_hash=new_hash,
        device_info=db_session.device_info,
        ip_address=db_session.ip_address,
        expires_at=datetime.now(timezone.utc) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(new_session)
    await session.flush()
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


async def logout(session: AsyncSession, refresh_token: str) -> None:
    """Revoke the session associated with the given refresh token."""
    token_hash = _hash_token(refresh_token)
    result = await session.execute(
        select(IamSession).where(IamSession.refresh_token_hash == token_hash)
    )
    db_session = result.scalar_one_or_none()
    if db_session and db_session.revoked_at is None:
        db_session.revoked_at = datetime.now(timezone.utc)
        await session.flush()


async def setup_totp(user: IamUser, session: AsyncSession) -> dict:
    """
    Generate a new TOTP secret, encrypt and store it, return the setup info.
    MFA is NOT activated until verify_totp_setup() is called.
    """
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_field(secret)
    user.mfa_enabled = False  # Not active until verified
    await session.flush()
    return {
        "totp_secret": secret,
        "qr_code_url": get_totp_uri(secret, user.email),
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
    user.mfa_enabled = True
    await session.flush()
    return True
