from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.platform.db.models.isolation_policy import CpTenantIsolationPolicy
from financeops.platform.db.models.tenant_packages import CpTenantPackageAssignment
from financeops.platform.db.models.tenant_quota_assignments import CpTenantQuotaAssignment
from financeops.platform.db.models.tenants import CpTenant
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


DEFAULT_QUOTAS: tuple[tuple[str, str, int, int, str], ...] = (
    ("api_requests", "tumbling", 60, 1200, "reject"),
    ("job_submissions", "sliding", 300, 300, "queue"),
    ("worker_active_jobs", "sliding", 60, 100, "queue"),
    ("storage_bytes", "sliding", 86400, 20_000_000_000, "reject"),
    ("export_bytes", "tumbling", 86400, 2_000_000_000, "throttle"),
    ("ai_inference_calls", "tumbling", 60, 200, "queue"),
)


async def onboard_tenant(
    session: AsyncSession,
    *,
    tenant_code: str,
    display_name: str,
    country_code: str,
    region: str,
    billing_tier: str,
    package_id: uuid.UUID,
    initiated_by: uuid.UUID,
    correlation_id: str,
) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    tenant = await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenant,
        tenant_id=tenant_id,
        record_data={
            "tenant_code": tenant_code,
            "display_name": display_name,
            "country_code": country_code,
            "region": region,
            "billing_tier": billing_tier,
        },
        values={
            "id": tenant_id,
            "tenant_code": tenant_code,
            "display_name": display_name,
            "country_code": country_code,
            "region": region,
            "billing_tier": billing_tier,
            "status": "active",
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="platform.tenant.onboarded",
            resource_type="cp_tenant",
            resource_id=str(tenant_id),
            new_value={"tenant_code": tenant_code, "billing_tier": billing_tier},
        ),
    )

    now = _now()
    await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantPackageAssignment,
        tenant_id=tenant_id,
        record_data={
            "package_id": str(package_id),
            "assignment_status": "active",
            "effective_from": now.isoformat(),
        },
        values={
            "package_id": package_id,
            "assignment_status": "active",
            "effective_from": now,
            "effective_to": None,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="platform.tenant.package.assigned",
            resource_type="cp_tenant_package_assignment",
            resource_id=str(package_id),
            new_value={"status": "active"},
        ),
    )

    for quota_type, window_type, window_seconds, max_value, enforcement_mode in DEFAULT_QUOTAS:
        await AuditWriter.insert_financial_record(
            session,
            model_class=CpTenantQuotaAssignment,
            tenant_id=tenant_id,
            record_data={
                "quota_type": quota_type,
                "window_seconds": window_seconds,
                "max_value": max_value,
                "effective_from": now.isoformat(),
            },
            values={
                "quota_policy_id": None,
                "quota_type": quota_type,
                "window_type": window_type,
                "window_seconds": window_seconds,
                "max_value": max_value,
                "enforcement_mode": enforcement_mode,
                "effective_from": now,
                "effective_to": None,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=initiated_by,
                action="platform.tenant.quota.assigned",
                resource_type="cp_tenant_quota_assignment",
                new_value={"quota_type": quota_type, "max_value": max_value},
            ),
        )

    await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantIsolationPolicy,
        tenant_id=tenant_id,
        record_data={
            "isolation_tier": "tier1",
            "route_version": 1,
            "effective_from": now.isoformat(),
        },
        values={
            "isolation_tier": "tier1",
            "db_cluster": "shared-primary",
            "schema_name": "public",
            "worker_pool": "shared-workers",
            "region": region,
            "migration_state": "active",
            "route_version": 1,
            "effective_from": now,
            "effective_to": None,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="platform.tenant.isolation.assigned",
            resource_type="cp_tenant_isolation_policy",
            new_value={"isolation_tier": "tier1", "route_version": 1},
        ),
    )

    return {
        "tenant_id": str(tenant.id),
        "status": "active",
        "onboarding_status": "completed",
    }


async def get_tenant(session: AsyncSession, *, tenant_id: uuid.UUID) -> CpTenant:
    result = await session.execute(
        select(CpTenant).where(CpTenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return tenant


async def validate_tenant_active(session: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    tenant = await get_tenant(session, tenant_id=tenant_id)
    if tenant.status != "active":
        raise ValidationError("Tenant is not active")
