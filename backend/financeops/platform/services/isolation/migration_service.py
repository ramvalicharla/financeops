from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenant_migration_events import CpTenantMigrationEvent
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def append_migration_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    isolation_policy_id: str,
    route_version: int,
    event_type: str,
    idempotency_key: str,
    metadata_json: dict[str, Any] | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpTenantMigrationEvent:
    existing_result = await session.execute(
        select(CpTenantMigrationEvent).where(
            CpTenantMigrationEvent.tenant_id == tenant_id,
            CpTenantMigrationEvent.route_version == route_version,
            CpTenantMigrationEvent.event_type == event_type,
            CpTenantMigrationEvent.idempotency_key == idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    seq_result = await session.execute(
        select(func.max(CpTenantMigrationEvent.event_seq)).where(
            CpTenantMigrationEvent.tenant_id == tenant_id,
            CpTenantMigrationEvent.route_version == route_version,
        )
    )
    seq = int(seq_result.scalar_one() or 0) + 1

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantMigrationEvent,
        tenant_id=tenant_id,
        record_data={
            "route_version": route_version,
            "event_type": event_type,
            "event_seq": seq,
            "idempotency_key": idempotency_key,
        },
        values={
            "isolation_policy_id": isolation_policy_id,
            "route_version": route_version,
            "event_seq": seq,
            "event_type": event_type,
            "event_time": _now(),
            "idempotency_key": idempotency_key,
            "metadata_json": metadata_json,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.isolation.migration_event.appended",
            resource_type="cp_tenant_migration_event",
            new_value={"route_version": route_version, "event_type": event_type, "event_seq": seq},
        ),
    )
