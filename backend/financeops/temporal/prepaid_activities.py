from __future__ import annotations

from typing import Any
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.services.prepaid import (
    build_journal_preview_for_run,
    finalize_run,
    generate_amortization_schedule_for_run,
    load_prepaids_for_run,
    mark_run_running,
    resolve_amortization_pattern_for_run,
    validate_lineage_for_run,
)
from financeops.temporal.prepaid_workflows import (
    PrepaidAmortizationWorkflowInput,
    PrepaidFinalizeInput,
)


def _uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="prepaid_mark_running_activity")
async def prepaid_mark_running_activity(payload: PrepaidAmortizationWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="prepaid_load_prepaids_activity")
async def prepaid_load_prepaids_activity(payload: PrepaidAmortizationWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await load_prepaids_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="prepaid_resolve_amortization_pattern_activity")
async def prepaid_resolve_amortization_pattern_activity(
    payload: PrepaidAmortizationWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    async with tenant_session(tenant_id) as session:
        result = await resolve_amortization_pattern_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
        )
        await session.commit()
    return result


@activity.defn(name="prepaid_generate_amortization_schedule_activity")
async def prepaid_generate_amortization_schedule_activity(
    payload: PrepaidAmortizationWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await generate_amortization_schedule_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="prepaid_build_journal_preview_activity")
async def prepaid_build_journal_preview_activity(payload: PrepaidAmortizationWorkflowInput) -> dict[str, int]:
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


@activity.defn(name="prepaid_validate_lineage_activity")
async def prepaid_validate_lineage_activity(payload: PrepaidAmortizationWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="prepaid_finalize_activity")
async def prepaid_finalize_activity(payload: PrepaidFinalizeInput) -> dict[str, Any]:
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
