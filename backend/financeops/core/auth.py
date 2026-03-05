from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthenticationError, AuthorizationError
from financeops.core.security import decode_token
from financeops.db.models.users import IamUser

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = None,  # Will be injected via dependency override in deps.py
) -> IamUser:
    """
    Decode JWT, load user from DB, verify is_active.
    Raises 401 if invalid/expired.
    NOTE: This function is called via get_current_user_dep in deps.py with session injected.
    """
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token missing subject")
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise AuthenticationError("Invalid token subject") from exc

    result = await session.execute(
        select(IamUser).where(IamUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("Account deactivated")
    return user


def get_current_tenant_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> uuid.UUID:
    """Extract tenant_id from JWT payload without hitting the DB."""
    payload = decode_token(token)
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise AuthenticationError("Token missing tenant_id")
    try:
        return uuid.UUID(tenant_id_str)
    except ValueError as exc:
        raise AuthenticationError("Invalid tenant_id in token") from exc


def require_role(*roles: str):
    """
    Returns a FastAPI dependency that checks user.role is in the allowed set.
    Raises 403 if not.
    """
    allowed = set(roles)

    async def _check_role(user: IamUser) -> IamUser:
        if user.role.value not in allowed:
            raise AuthorizationError(
                f"Role '{user.role.value}' not allowed. Required: {allowed}"
            )
        return user

    return _check_role


async def require_mfa(user: IamUser) -> IamUser:
    """
    Dependency that raises 403 if MFA is not enabled on the account.
    Add to routes that require MFA to be confirmed.
    """
    if not user.mfa_enabled:
        raise AuthorizationError(
            "Multi-factor authentication must be enabled to access this resource"
        )
    return user
