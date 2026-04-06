from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    require_platform_admin,
    require_platform_owner,
)
from financeops.db.models.users import IamUser
from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.role_permissions import CpRolePermission
from financeops.platform.db.models.roles import CpRole
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment
from financeops.platform.schemas.rbac import (
    PermissionCreate,
    RoleCreate,
    RolePermissionGrant,
    UserRoleAssignmentCreate,
)
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import assign_user_role, create_role

router = APIRouter()


@router.get("/roles")
async def list_roles_endpoint(
    include_inactive: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> list[dict]:
    stmt = select(CpRole).where(CpRole.tenant_id == user.tenant_id)
    if not include_inactive:
        stmt = stmt.where(CpRole.is_active.is_(True))
    rows = (await session.execute(stmt.order_by(CpRole.role_code.asc()))).scalars().all()
    return [
        {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "role_code": row.role_code,
            "role_scope": row.role_scope,
            "inherits_role_id": str(row.inherits_role_id) if row.inherits_role_id else None,
            "is_active": row.is_active,
            "description": row.description,
        }
        for row in rows
    ]


@router.get("/permissions")
async def list_permissions_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> list[dict]:
    rows = (
        await session.execute(
            select(CpPermission).order_by(CpPermission.permission_code.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "permission_code": row.permission_code,
            "resource_type": row.resource_type,
            "action": row.action,
            "description": row.description,
        }
        for row in rows
    ]


@router.get("/role-permissions")
async def list_role_permissions_endpoint(
    role_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> list[dict]:
    stmt = select(CpRolePermission).where(CpRolePermission.tenant_id == user.tenant_id)
    if role_id is not None:
        stmt = stmt.where(CpRolePermission.role_id == role_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "role_id": str(row.role_id),
            "permission_id": str(row.permission_id),
            "effect": row.effect,
        }
        for row in rows
    ]


@router.get("/assignments")
async def list_assignments_endpoint(
    user_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> list[dict]:
    stmt = select(CpUserRoleAssignment).where(
        CpUserRoleAssignment.tenant_id == user.tenant_id
    )
    if user_id is not None:
        stmt = stmt.where(CpUserRoleAssignment.user_id == user_id)
    rows = (
        await session.execute(
            stmt.order_by(CpUserRoleAssignment.effective_from.desc())
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "user_id": str(row.user_id),
            "role_id": str(row.role_id),
            "context_type": row.context_type,
            "context_id": str(row.context_id) if row.context_id else None,
            "is_active": row.is_active,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "assigned_by": str(row.assigned_by) if row.assigned_by else None,
        }
        for row in rows
    ]


@router.post("/roles")
async def create_role_endpoint(
    body: RoleCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
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
    user: IamUser = Depends(require_platform_owner),
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
    user: IamUser = Depends(require_platform_owner),
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
    user: IamUser = Depends(require_platform_owner),
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
