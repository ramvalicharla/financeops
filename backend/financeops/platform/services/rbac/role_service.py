from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.roles import CpRole
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_code: str,
    role_scope: str,
    inherits_role_id: uuid.UUID | None,
    is_active: bool,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpRole:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpRole,
        tenant_id=tenant_id,
        record_data={"role_code": role_code, "role_scope": role_scope},
        values={
            "role_code": role_code,
            "role_scope": role_scope,
            "inherits_role_id": inherits_role_id,
            "is_active": is_active,
            "description": None,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.rbac.role.created",
            resource_type="cp_role",
            new_value={"role_code": role_code, "role_scope": role_scope, "correlation_id": correlation_id},
        ),
    )


async def assign_user_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    context_type: str,
    context_id: uuid.UUID | None,
    effective_from: datetime,
    effective_to: datetime | None,
    assigned_by: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpUserRoleAssignment:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpUserRoleAssignment,
        tenant_id=tenant_id,
        record_data={
            "user_id": str(user_id),
            "role_id": str(role_id),
            "context_type": context_type,
            "effective_from": effective_from.isoformat(),
        },
        values={
            "user_id": user_id,
            "role_id": role_id,
            "context_type": context_type,
            "context_id": context_id,
            "is_active": True,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "assigned_by": assigned_by,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.rbac.user_role.assigned",
            resource_type="cp_user_role_assignment",
            new_value={"user_id": str(user_id), "role_id": str(role_id), "context_type": context_type},
        ),
    )


async def assign_user_role_now(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    context_type: str,
    context_id: uuid.UUID | None,
    assigned_by: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpUserRoleAssignment:
    return await assign_user_role(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role_id,
        context_type=context_type,
        context_id=context_id,
        effective_from=_now(),
        effective_to=None,
        assigned_by=assigned_by,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
