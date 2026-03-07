from __future__ import annotations

from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.platform.services.isolation.migration_service import append_migration_event
from financeops.platform.temporal.tenant_migration_workflows import TenantMigrationWorkflowInput


def _parse_uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="tenant_migration_mark_running_activity")
async def tenant_migration_mark_running_activity(payload: TenantMigrationWorkflowInput) -> dict:
    tenant_id = _parse_uuid(payload.tenant_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        event = await append_migration_event(
            session,
            tenant_id=tenant_id,
            isolation_policy_id=f"tenant:{payload.tenant_id}",
            route_version=payload.route_version,
            event_type="migration_running",
            idempotency_key="migration-running",
            metadata_json={"config_hash": payload.config_hash},
            actor_user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"event_seq": event.event_seq, "event_type": event.event_type}


@activity.defn(name="tenant_migration_finalize_activity")
async def tenant_migration_finalize_activity(payload: TenantMigrationWorkflowInput) -> dict:
    tenant_id = _parse_uuid(payload.tenant_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        event = await append_migration_event(
            session,
            tenant_id=tenant_id,
            isolation_policy_id=f"tenant:{payload.tenant_id}",
            route_version=payload.route_version,
            event_type="migration_completed",
            idempotency_key="migration-completed",
            metadata_json={"config_hash": payload.config_hash},
            actor_user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"event_seq": event.event_seq, "event_type": event.event_type}
