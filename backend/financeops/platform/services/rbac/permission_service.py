from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.role_permissions import CpRolePermission
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def create_permission(
    session: AsyncSession,
    *,
    actor_tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    permission_code: str,
    resource_type: str,
    action: str,
    description: str | None,
) -> CpPermission:
    return await AuditWriter.insert_record(
        session,
        record=CpPermission(
            permission_code=permission_code,
            resource_type=resource_type,
            action=action,
            description=description,
        ),
        audit=AuditEvent(
            tenant_id=actor_tenant_id,
            user_id=actor_user_id,
            action="platform.rbac.permission.created",
            resource_type="cp_permission",
            new_value={"permission_code": permission_code, "action": action},
        ),
    )


async def grant_role_permission(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    permission_id: uuid.UUID,
    effect: str,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpRolePermission:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpRolePermission,
        tenant_id=tenant_id,
        record_data={"role_id": str(role_id), "permission_id": str(permission_id), "effect": effect},
        values={
            "role_id": role_id,
            "permission_id": permission_id,
            "effect": effect,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.rbac.role_permission.granted",
            resource_type="cp_role_permission",
            new_value={"role_id": str(role_id), "permission_id": str(permission_id), "effect": effect, "correlation_id": correlation_id},
        ),
    )
