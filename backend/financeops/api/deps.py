from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import Settings, get_settings
from financeops.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
)
from financeops.core.security import decode_token
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_redis_pool: aioredis.Redis | None = None
_PUBLIC_AUTH_BYPASS_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/refresh",
}
_ONBOARDING_BYPASS_PREFIXES = (
    "/api/v1/org-setup",
    "/api/v1/platform/org",
    "/api/v1/platform/entities",
)


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session with RLS context set from request middleware.
    Rolls back on exception, closes on exit.
    """
    log.info("DEPENDENCY HIT: get_async_session")
    path = request.url.path
    if path in _PUBLIC_AUTH_BYPASS_PATHS:
        log.info("Public route bypass auth: %s", path)
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.flush()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        return

    tenant_id = str(getattr(request.state, "tenant_id", "") or "")
    if not tenant_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            tenant_id = str(payload.get("tenant_id", "") or "")
    if not tenant_id:
        auditor_token = request.headers.get("X-Auditor-Token", "").strip()
        if auditor_token:
            tenant_prefix = auditor_token.split(".", 1)[0]
            try:
                tenant_id = str(uuid.UUID(tenant_prefix))
            except ValueError:
                tenant_id = ""
    if not tenant_id:
        raise AuthenticationError(
            "tenant_id missing from token - RLS context cannot be set"
        )
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, tenant_id)
            yield session
            await session.flush()
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)
            await session.close()


async def get_session_with_rls(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a DB session with the tenant RLS context set from the JWT.
    """
    tenant_id = str(getattr(request.state, "tenant_id", "") or "")
    if not tenant_id:
        payload = decode_token(token)
        tenant_id = str(payload.get("tenant_id", "") or "")
    if not tenant_id:
        raise AuthenticationError(
            "tenant_id missing from token - RLS context cannot be set"
        )

    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, tenant_id)
            yield session
            await session.flush()
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)
            await session.close()


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_async_session),
) -> IamUser:
    """Decode JWT, load user from DB, verify is_active. Raises 401 if invalid."""
    log.info("DEPENDENCY HIT: get_current_user")
    if request.method.upper() == "OPTIONS":
        log.info("OPTIONS bypass at dependency: %s", request.url.path)
        raise HTTPException(status_code=204, detail=None)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise AuthenticationError("Token missing tenant_id")
    try:
        jwt_tenant_id = uuid.UUID(str(tenant_id_str))
    except ValueError as exc:
        raise AuthenticationError("Invalid tenant_id in token") from exc
    token_scope = payload.get("scope")
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
    if user.tenant_id is None:
        raise AuthenticationError("User missing tenant_id")
    if user.tenant_id != jwt_tenant_id:
        raise AuthenticationError("Token tenant mismatch")

    # Keep tenant identity consistent across downstream dependencies/session context.
    request.state.tenant_id = str(jwt_tenant_id)
    setattr(user, "_jwt_tenant_id", jwt_tenant_id)

    if request.url.path.startswith("/api/v1/org-setup"):
        log.info("MFA bypass for onboarding: %s", request.url.path)
        log.info("MFA BYPASS ACTIVE")
        return user

    if token_scope == "mfa_setup_only":
        raise HTTPException(
            status_code=403,
            detail="MFA setup required before accessing this resource. Complete MFA setup at /api/v1/auth/mfa/setup",
        )
    if user.force_mfa_setup and not user.mfa_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "mfa_setup_required",
                "message": "MFA setup required",
                "setup_url": "/mfa/setup",
            },
        )
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


async def get_current_tenant(
    request: Request,
    user: IamUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IamTenant:
    log.info("DEPENDENCY HIT: get_current_tenant")
    if request.method.upper() == "OPTIONS":
        log.info("OPTIONS bypass at dependency: %s", request.url.path)
        raise HTTPException(status_code=204, detail=None)
    log.info("PATH HIT: %s", request.url.path)
    jwt_tenant_id = getattr(user, "_jwt_tenant_id", None)
    if jwt_tenant_id is None:
        raise AuthenticationError("Missing JWT tenant context")
    tenant = (
        await session.execute(select(IamTenant).where(IamTenant.id == jwt_tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise AuthenticationError("Tenant not found")
    log.info(
        "Tenant resolution jwt_tenant_id=%s resolved_tenant_id=%s",
        jwt_tenant_id,
        tenant.id,
    )
    if request.url.path.startswith(_ONBOARDING_BYPASS_PREFIXES):
        log.info("BYPASS ACTIVE")
        return tenant
    return tenant


async def require_org_setup(
    request: Request,
    current_tenant: IamTenant = Depends(get_current_tenant),
) -> IamTenant:
    log.info("DEPENDENCY HIT: require_org_setup")
    if request.method.upper() == "OPTIONS":
        log.info("OPTIONS bypass at dependency: %s", request.url.path)
        return current_tenant
    log.info("PATH HIT: %s", request.url.path)
    if request.url.path.startswith(_ONBOARDING_BYPASS_PREFIXES):
        log.info("BYPASS ACTIVE")
        log.info("Bypassing onboarding check for: %s", request.url.path)
        return current_tenant
    if current_tenant.is_platform_tenant:
        return current_tenant
    if not current_tenant.org_setup_complete:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ORG_SETUP_REQUIRED",
                "message": (
                    "Organisation setup must be completed before accessing this "
                    "feature."
                ),
                "current_step": current_tenant.org_setup_step,
            },
        )
    return current_tenant


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


async def require_director(
    current_user: IamUser = Depends(get_current_user),
) -> IamUser:
    if current_user.role not in {
        UserRole.director,
        UserRole.finance_leader,
        UserRole.platform_owner,
    }:
        raise HTTPException(status_code=403, detail="Director or Finance Leader role required")
    return current_user


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
