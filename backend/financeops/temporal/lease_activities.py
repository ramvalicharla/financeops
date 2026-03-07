from __future__ import annotations

from typing import Any
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.services.lease import (
    build_journal_preview_for_run,
    build_payment_timeline_for_run,
    calculate_present_value_for_run,
    finalize_run,
    generate_liability_schedule_for_run,
    generate_rou_schedule_for_run,
    load_leases_and_payments_for_run,
    mark_run_running,
    validate_lineage_for_run,
)
from financeops.temporal.lease_workflows import LeaseAccountingWorkflowInput, LeaseFinalizeInput


def _uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="lease_mark_running_activity")
async def lease_mark_running_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, Any]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        event = await mark_run_running(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"event_type": event.event_type, "event_seq": event.event_seq}


@activity.defn(name="lease_load_leases_and_payments_activity")
async def lease_load_leases_and_payments_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await load_leases_and_payments_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_build_payment_timeline_activity")
async def lease_build_payment_timeline_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await build_payment_timeline_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_calculate_present_value_activity")
async def lease_calculate_present_value_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, str]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await calculate_present_value_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_generate_liability_schedule_activity")
async def lease_generate_liability_schedule_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await generate_liability_schedule_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_generate_rou_schedule_activity")
async def lease_generate_rou_schedule_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await generate_rou_schedule_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_build_journal_preview_activity")
async def lease_build_journal_preview_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await build_journal_preview_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="lease_validate_lineage_activity")
async def lease_validate_lineage_activity(payload: LeaseAccountingWorkflowInput) -> dict[str, Any]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    async with tenant_session(tenant_id) as session:
        result = await validate_lineage_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
        )
        await session.commit()
    return result.as_metadata()


@activity.defn(name="lease_finalize_activity")
async def lease_finalize_activity(payload: LeaseFinalizeInput) -> dict[str, Any]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        event = await finalize_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
            event_type=payload.event_type,
            metadata_json=payload.metadata_json,
        )
        await session.commit()
    return {
        "event_type": event.event_type,
        "event_seq": event.event_seq,
        "metadata": event.metadata_json,
    }
