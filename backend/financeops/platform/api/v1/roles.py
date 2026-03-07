from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.platform.schemas.rbac import (
    PermissionCreate,
    RoleCreate,
    RolePermissionGrant,
    UserRoleAssignmentCreate,
)
from financeops.platform.services.rbac.permission_service import create_permission, grant_role_permission
from financeops.platform.services.rbac.role_service import assign_user_role, create_role

router = APIRouter()


@router.post("/roles")
async def create_role_endpoint(
    body: RoleCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    role = await create_role(
        session,
        tenant_id=user.tenant_id,
        role_code=body.role_code,
        role_scope=body.role_scope,
        inherits_role_id=body.inherits_role_id,
        is_active=body.is_active,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(role.id), "role_code": role.role_code}


@router.post("/permissions")
async def create_permission_endpoint(
    body: PermissionCreate,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    permission = await create_permission(
        session,
        actor_tenant_id=user.tenant_id,
        actor_user_id=user.id,
        permission_code=body.permission_code,
        resource_type=body.resource_type,
        action=body.action,
        description=body.description,
    )
    await session.commit()
    return {"id": str(permission.id), "permission_code": permission.permission_code}


@router.post("/role-permissions")
async def grant_role_permission_endpoint(
    body: RolePermissionGrant,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    grant = await grant_role_permission(
        session,
        tenant_id=user.tenant_id,
        role_id=body.role_id,
        permission_id=body.permission_id,
        effect=body.effect,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(grant.id), "effect": grant.effect}


@router.post("/assignments")
async def assign_user_role_endpoint(
    body: UserRoleAssignmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    assignment = await assign_user_role(
        session,
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        role_id=body.role_id,
        context_type=body.context_type,
        context_id=body.context_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        assigned_by=body.assigned_by,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(assignment.id)}
