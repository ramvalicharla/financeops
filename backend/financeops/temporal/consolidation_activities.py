from __future__ import annotations

from typing import Any
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.services.consolidation import (
    aggregate_results_for_run,
    apply_fx_for_run,
    compute_eliminations_for_run,
    finalize_run,
    mark_run_running,
    match_intercompany_for_run,
    prepare_entities_for_run,
)
from financeops.temporal.consolidation_workflows import (
    ConsolidationFinalizeInput,
    ConsolidationWorkflowInput,
)


def _parse_uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="consolidation_mark_running_activity")
async def consolidation_mark_running_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        event = await mark_run_running(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"event_seq": event.event_seq, "event_type": event.event_type}


@activity.defn(name="consolidation_prepare_entities_activity")
async def consolidation_prepare_entities_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        count = await prepare_entities_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"entity_count": count}


@activity.defn(name="consolidation_apply_fx_activity")
async def consolidation_apply_fx_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        count = await apply_fx_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"line_item_count": count}


@activity.defn(name="consolidation_match_ic_activity")
async def consolidation_match_ic_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        count = await match_intercompany_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"intercompany_pair_count": count}


@activity.defn(name="consolidation_compute_eliminations_activity")
async def consolidation_compute_eliminations_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        count = await compute_eliminations_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return {"elimination_count": count}


@activity.defn(name="consolidation_aggregate_results_activity")
async def consolidation_aggregate_results_activity(payload: ConsolidationWorkflowInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        output = await aggregate_results_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return output


@activity.defn(name="consolidation_finalize_activity")
async def consolidation_finalize_activity(payload: ConsolidationFinalizeInput) -> dict[str, Any]:
    tenant_id = _parse_uuid(payload.tenant_id)
    run_id = _parse_uuid(payload.run_id)
    requested_by = _parse_uuid(payload.requested_by)
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
