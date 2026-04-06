from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.platform.services.rbac.permission_matrix import PERMISSIONS, ROLE_ALIASES

log = logging.getLogger(__name__)


def _normalize(value: str) -> str:
    return value.strip().lower()


def _get_runtime_role(user: IamUser) -> str:
    role = getattr(user.role, "value", user.role)
    return str(role)


def _resolve_canonical_roles(runtime_role: str) -> set[str]:
    resolved: set[str] = set()
    normalized_role = _normalize(runtime_role)
    for canonical_role, aliases in ROLE_ALIASES.items():
        if normalized_role in {_normalize(alias) for alias in aliases}:
            resolved.add(canonical_role)
    return resolved


async def has_permission(
    user: IamUser,
    permission: str,
    context: dict[str, Any] | None = None,
) -> bool:
    entry = PERMISSIONS.get(permission)
    if entry is None:
        log.debug("permission_check permission=%s decision=deny reason=permission_undefined", permission)
        return False

    context = context or {}
    runtime_role = _get_runtime_role(user)
    resolved_roles = _resolve_canonical_roles(runtime_role)

    role_allowed = bool(
        resolved_roles.intersection(entry["roles"])
        or _normalize(runtime_role) in {_normalize(role) for role in entry["runtime_roles"]}
    )
    if not role_allowed:
        log.debug(
            "permission_check permission=%s decision=deny reason=role_mismatch runtime_role=%s resolved_roles=%s",
            permission,
            runtime_role,
            sorted(resolved_roles),
        )
        return False

    session: AsyncSession | None = context.get("session")
    if entry["entitlement_keys"] and session is not None:
        entitlement_service = EntitlementService(session)
        entitled = False
        for entitlement_key in entry["entitlement_keys"]:
            decision = await entitlement_service.check_entitlement(
                tenant_id=user.tenant_id,
                feature_name=entitlement_key,
                quantity=1,
            )
            if decision.allowed:
                entitled = True
                break
        if not entitled:
            log.debug(
                "permission_check permission=%s decision=deny reason=missing_entitlement entitlement_keys=%s tenant_id=%s",
                permission,
                entry["entitlement_keys"],
                user.tenant_id,
            )
            return False

    log.debug(
        "permission_check permission=%s decision=allow runtime_role=%s resolved_roles=%s",
        permission,
        runtime_role,
        sorted(resolved_roles),
    )
    return True


def require_permission(
    permission: str,
    *,
    strict: bool = False,
) -> Callable[[Request, AsyncSession, IamUser], Awaitable[IamUser]]:
    async def _dependency(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
        user: IamUser = Depends(get_current_user),
    ) -> IamUser:
        allowed = await has_permission(
            user,
            permission,
            {
                "request": request,
                "session": session,
            },
        )
        if allowed:
            return user
        if strict:
            raise AuthorizationError(f"{permission} permission required")
        log.debug(
            "permission_validation_only permission=%s decision=allow_legacy path=%s user_id=%s",
            permission,
            request.url.path,
            user.id,
        )
        return user

    return _dependency
