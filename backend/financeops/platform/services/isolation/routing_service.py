from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.platform.db.models.isolation_policy import CpTenantIsolationPolicy
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_isolation_route(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    isolation_tier: str,
    db_cluster: str,
    schema_name: str,
    worker_pool: str,
    region: str,
    migration_state: str,
    route_version: int,
    effective_from: datetime,
    effective_to: datetime | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpTenantIsolationPolicy:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantIsolationPolicy,
        tenant_id=tenant_id,
        record_data={
            "route_version": route_version,
            "db_cluster": db_cluster,
            "schema_name": schema_name,
            "worker_pool": worker_pool,
        },
        values={
            "isolation_tier": isolation_tier,
            "db_cluster": db_cluster,
            "schema_name": schema_name,
            "worker_pool": worker_pool,
            "region": region,
            "migration_state": migration_state,
            "route_version": route_version,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.isolation.route.created",
            resource_type="cp_tenant_isolation_policy",
            new_value={"route_version": route_version, "migration_state": migration_state},
        ),
    )


async def resolve_isolation_route(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    as_of: datetime | None = None,
) -> CpTenantIsolationPolicy:
    query_time = as_of or _now()
    result = await session.execute(
        select(CpTenantIsolationPolicy)
        .where(
            CpTenantIsolationPolicy.tenant_id == tenant_id,
            CpTenantIsolationPolicy.effective_from <= query_time,
            (CpTenantIsolationPolicy.effective_to.is_(None) | (CpTenantIsolationPolicy.effective_to > query_time)),
        )
        .order_by(CpTenantIsolationPolicy.route_version.desc())
    )
    route = result.scalars().first()
    if route is None:
        raise NotFoundError("Isolation route unavailable")
    if not all([route.db_cluster, route.schema_name, route.worker_pool, route.region]):
        raise ValidationError("Isolation route has missing attributes")
    return route
