from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.quota_policies import CpQuotaPolicy
from financeops.platform.db.models.tenant_quota_assignments import CpTenantQuotaAssignment
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_quota_policy(
    session: AsyncSession,
    *,
    actor_tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    quota_type: str,
    window_type: str,
    window_seconds: int,
    default_max_value: int,
    default_enforcement_mode: str,
    description: str | None,
) -> CpQuotaPolicy:
    return await AuditWriter.insert_record(
        session,
        record=CpQuotaPolicy(
            quota_type=quota_type,
            window_type=window_type,
            window_seconds=window_seconds,
            default_max_value=default_max_value,
            default_enforcement_mode=default_enforcement_mode,
            description=description,
        ),
        audit=AuditEvent(
            tenant_id=actor_tenant_id,
            user_id=actor_user_id,
            action="platform.quota.policy.created",
            resource_type="cp_quota_policy",
            new_value={"quota_type": quota_type, "window_seconds": window_seconds},
        ),
    )


async def assign_quota_to_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quota_type: str,
    window_type: str,
    window_seconds: int,
    max_value: int,
    enforcement_mode: str,
    effective_from: datetime | None,
    effective_to: datetime | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpTenantQuotaAssignment:
    active_from = effective_from or _now()
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantQuotaAssignment,
        tenant_id=tenant_id,
        record_data={
            "quota_type": quota_type,
            "window_seconds": window_seconds,
            "max_value": max_value,
            "effective_from": active_from.isoformat(),
        },
        values={
            "quota_policy_id": None,
            "quota_type": quota_type,
            "window_type": window_type,
            "window_seconds": window_seconds,
            "max_value": max_value,
            "enforcement_mode": enforcement_mode,
            "effective_from": active_from,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.quota.assignment.created",
            resource_type="cp_tenant_quota_assignment",
            new_value={"quota_type": quota_type, "max_value": max_value},
        ),
    )
