from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import Settings, get_settings
from financeops.core.exceptions import AuthenticationError, AuthorizationError, InsufficientCreditsError
from financeops.core.security import decode_token
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_redis_pool: aioredis.Redis | None = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session with RLS context set from the request token.
    Rolls back on exception, closes on exit.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session_with_rls(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a DB session with the tenant RLS context set from the JWT.
    """
    payload = decode_token(token)
    tenant_id = payload.get("tenant_id", "")
    async with AsyncSessionLocal() as session:
        try:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_async_session),
) -> IamUser:
    """Decode JWT, load user from DB, verify is_active. Raises 401 if invalid."""
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
    result = await session.execute(select(IamUser).where(IamUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("Account deactivated")
    return user


def get_current_tenant_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> uuid.UUID:
    """Extract tenant_id from JWT without DB call."""
    payload = decode_token(token)
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise AuthenticationError("Token missing tenant_id")
    try:
        return uuid.UUID(tenant_id_str)
    except ValueError as exc:
        raise AuthenticationError("Invalid tenant_id in token") from exc


def require_finance_leader(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    allowed = {UserRole.super_admin, UserRole.finance_leader}
    if user.role not in allowed:
        raise AuthorizationError("finance_leader or higher required")
    return user


def require_finance_team(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    allowed = {UserRole.super_admin, UserRole.finance_leader, UserRole.finance_team}
    if user.role not in allowed:
        raise AuthorizationError("finance_team or higher required")
    return user


def require_auditor_or_above(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    allowed = {
        UserRole.super_admin,
        UserRole.finance_leader,
        UserRole.finance_team,
        UserRole.auditor,
    }
    if user.role not in allowed:
        raise AuthorizationError("auditor or higher required")
    return user


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a Redis connection from the async pool."""
    global _redis_pool
    from financeops.config import settings
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
    yield _redis_pool


def get_settings_dep() -> Settings:
    return get_settings()
