from __future__ import annotations

from typing import Any
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.services.revenue import (
    allocate_contract_value_for_run,
    build_journal_preview_for_run,
    finalize_run,
    generate_revenue_schedule_for_run,
    load_contracts_and_obligations_for_run,
    mark_run_running,
    validate_lineage_for_run,
)
from financeops.temporal.revenue_workflows import RevenueFinalizeInput, RevenueRecognitionWorkflowInput


def _uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="revenue_mark_running_activity")
async def revenue_mark_running_activity(payload: RevenueRecognitionWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="revenue_load_contracts_and_obligations_activity")
async def revenue_load_contracts_and_obligations_activity(
    payload: RevenueRecognitionWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await load_contracts_and_obligations_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="revenue_allocate_contract_value_activity")
async def revenue_allocate_contract_value_activity(
    payload: RevenueRecognitionWorkflowInput,
) -> dict[str, str]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await allocate_contract_value_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="revenue_generate_revenue_schedule_activity")
async def revenue_generate_revenue_schedule_activity(
    payload: RevenueRecognitionWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await generate_revenue_schedule_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="revenue_build_journal_preview_activity")
async def revenue_build_journal_preview_activity(payload: RevenueRecognitionWorkflowInput) -> dict[str, int]:
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


@activity.defn(name="revenue_validate_lineage_activity")
async def revenue_validate_lineage_activity(payload: RevenueRecognitionWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="revenue_finalize_activity")
async def revenue_finalize_activity(payload: RevenueFinalizeInput) -> dict[str, Any]:
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
