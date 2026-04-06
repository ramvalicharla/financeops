from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
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
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.services.enforcement.auth_modes import (
    AuthMode,
    PUBLIC_ROUTE_PATHS,
)
from financeops.platform.services.feature_flags.flag_service import evaluate_feature_flag
from financeops.platform.services.rbac.evaluator import evaluate_permission
from financeops.platform.services.rbac.user_plane import (
    TenantRole,
    has_minimum_tenant_role,
)

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_redis_pool: aioredis.Redis | None = None
_ONBOARDING_BYPASS_PREFIXES = (
    "/api/v1/org-setup",
    "/api/v1/platform/org",
    "/api/v1/platform/entities",
)
_PLATFORM_ADMIN_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
}
_PLATFORM_OWNER_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
}
_FINANCE_APPROVER_ROLES = _PLATFORM_ADMIN_ROLES | {
    UserRole.finance_leader,
}
_FINANCE_REVIEWER_ROLES = _FINANCE_APPROVER_ROLES | {
    UserRole.finance_team,
}
_SUPPORT_ROLES = _PLATFORM_ADMIN_ROLES | {
    UserRole.platform_support,
}
_DYNAMIC_PERMISSION_FALLBACK_REASONS = {
    "permission_not_defined",
    "no_role_assignments",
    "no_matching_permissions",
    "no_effective_permission",
}


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session with RLS context set from request middleware.
    Rolls back on exception, closes on exit.
    """
    path = request.url.path
    if path in PUBLIC_ROUTE_PATHS:
        async with AsyncSessionLocal() as session:
            try:
                request.state.auth_mode = AuthMode.PUBLIC.value
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
    request.state.auth_mode = AuthMode.USER.value
    setattr(user, "_jwt_tenant_id", jwt_tenant_id)

    if request.url.path.startswith("/api/v1/org-setup"):
        log.info("MFA bypass for onboarding: %s", request.url.path)
        return user

    if token_scope == "mfa_setup_only":
        raise HTTPException(
            status_code=403,
            detail="MFA setup required before accessing this resource. Complete MFA setup at /api/v1/auth/mfa/setup",
        )
    if token_scope == "password_change_only":
        raise HTTPException(
            status_code=403,
            detail="Password change required before accessing this resource. Complete password update at /auth/change-password",
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
        log.info("Bypassing onboarding check for: %s", request.url.path)
        return tenant
    return tenant


async def require_org_setup(
    request: Request,
    current_tenant: IamTenant = Depends(get_current_tenant),
) -> IamTenant:
    if request.method.upper() == "OPTIONS":
        return current_tenant
    if request.url.path.startswith(_ONBOARDING_BYPASS_PREFIXES):
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


def require_entitlement(
    feature_name: str,
    *,
    quantity: int = 1,
    record_usage: bool = False,
):
    async def _dependency(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
        user: IamUser = Depends(get_current_user),
    ) -> dict[str, object]:
        if request.method.upper() == "OPTIONS":
            log.info("OPTIONS bypass at dependency: %s", request.url.path)
            return {"allowed": True, "feature_name": feature_name}
        service = EntitlementService(session)
        decision = await service.check_entitlement(
            tenant_id=user.tenant_id,
            feature_name=feature_name,
            quantity=quantity,
        )
        if not decision.allowed:
            raise AuthorizationError(
                f"Entitlement denied for feature '{feature_name}': {decision.reason}"
            )
        module_row = (
            await session.execute(
                select(CpModuleRegistry).where(
                    CpModuleRegistry.module_code == feature_name,
                    CpModuleRegistry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if module_row is not None:
            entity_id_raw = (
                getattr(request.state, "active_entity_id", None)
                or request.headers.get("X-Entity-ID")
            )
            entity_id = None
            if entity_id_raw:
                try:
                    entity_id = uuid.UUID(str(entity_id_raw))
                except ValueError:
                    entity_id = None
            flag_eval = await evaluate_feature_flag(
                session,
                tenant_id=user.tenant_id,
                module_id=module_row.id,
                flag_key="enabled",
                request_fingerprint=str(
                    getattr(request.state, "request_id", None)
                    or request.url.path
                ),
                user_id=user.id,
                entity_id=entity_id,
            )
            # Only enforce when a flag has been explicitly configured.
            if flag_eval.get("selected_flag_id") and not flag_eval.get("enabled"):
                raise AuthorizationError(
                    f"Feature flag disabled for '{feature_name}'"
                )
        if record_usage:
            await service.record_usage_event(
                tenant_id=user.tenant_id,
                feature_name=feature_name,
                usage_quantity=max(quantity, 1),
                reference_type="api",
                reference_id=request.url.path,
                actor_user_id=user.id,
            )
        return {
            "allowed": decision.allowed,
            "feature_name": decision.feature_name,
            "access_type": decision.access_type,
            "effective_limit": decision.effective_limit,
            "used": decision.used,
            "remaining": decision.remaining,
            "reason": decision.reason,
        }

    return _dependency


def require_finance_leader(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    allowed = _FINANCE_APPROVER_ROLES
    if user.role not in allowed:
        raise AuthorizationError("finance_approver role required")
    return user


def require_finance_team(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    allowed = _FINANCE_REVIEWER_ROLES
    if user.role not in allowed:
        raise AuthorizationError("finance_reviewer or higher required")
    return user


def require_platform_admin(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    if user.role not in _PLATFORM_ADMIN_ROLES:
        raise AuthorizationError("platform_admin role required")
    return user


def require_platform_owner(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    if user.role not in _PLATFORM_OWNER_ROLES:
        raise AuthorizationError("platform_owner role required")
    return user


def require_support_or_admin(
    user: IamUser = Depends(get_current_user),
) -> IamUser:
    if user.role not in _SUPPORT_ROLES:
        raise AuthorizationError("platform_support or admin role required")
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


def require_tenant_minimum_role(minimum_role: TenantRole):
    async def _dependency(
        user: IamUser = Depends(get_current_user),
    ) -> IamUser:
        if not has_minimum_tenant_role(user.role, minimum_role):
            raise AuthorizationError(f"{minimum_role.value} role required")
        return user

    return _dependency


def require_user_plane_permission(
    *,
    resource_type: str,
    action: str,
    fallback_roles: set[UserRole],
    fallback_error_message: str,
):
    async def _dependency(
        session: AsyncSession = Depends(get_async_session),
        user: IamUser = Depends(get_current_user),
    ) -> IamUser:
        evaluation = await evaluate_permission(
            session,
            tenant_id=user.tenant_id,
            user_id=user.id,
            resource_type=resource_type,
            action=action,
            context_scope={"tenant": user.tenant_id},
            execution_timestamp=datetime.now(UTC),
        )
        if evaluation.allowed:
            return user
        if evaluation.reason == "deny_over_allow":
            raise AuthorizationError(f"{resource_type}.{action} denied")
        if evaluation.reason not in _DYNAMIC_PERMISSION_FALLBACK_REASONS:
            raise AuthorizationError(f"{resource_type}.{action} denied")
        if user.role not in fallback_roles:
            raise AuthorizationError(fallback_error_message)
        return user

    return _dependency


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
