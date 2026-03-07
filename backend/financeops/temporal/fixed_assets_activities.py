from __future__ import annotations

from typing import Any
from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.services.fixed_assets import (
    apply_impairment_and_disposal_events_for_run,
    build_journal_preview_for_run,
    finalize_run,
    generate_depreciation_schedule_for_run,
    load_assets_for_run,
    mark_run_running,
    validate_lineage_for_run,
)
from financeops.temporal.fixed_assets_workflows import (
    FixedAssetsFinalizeInput,
    FixedAssetsWorkflowInput,
)


def _uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="fixed_assets_mark_running_activity")
async def fixed_assets_mark_running_activity(payload: FixedAssetsWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="fixed_assets_load_assets_activity")
async def fixed_assets_load_assets_activity(payload: FixedAssetsWorkflowInput) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await load_assets_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="fixed_assets_generate_depreciation_schedule_activity")
async def fixed_assets_generate_depreciation_schedule_activity(
    payload: FixedAssetsWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await generate_depreciation_schedule_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="fixed_assets_apply_impairment_disposal_activity")
async def fixed_assets_apply_impairment_disposal_activity(
    payload: FixedAssetsWorkflowInput,
) -> dict[str, int]:
    tenant_id = _uuid(payload.tenant_id)
    run_id = _uuid(payload.run_id)
    requested_by = _uuid(payload.requested_by)
    async with tenant_session(tenant_id) as session:
        result = await apply_impairment_and_disposal_events_for_run(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=requested_by,
            correlation_id=payload.correlation_id,
        )
        await session.commit()
    return result


@activity.defn(name="fixed_assets_build_journal_preview_activity")
async def fixed_assets_build_journal_preview_activity(payload: FixedAssetsWorkflowInput) -> dict[str, int]:
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


@activity.defn(name="fixed_assets_validate_lineage_activity")
async def fixed_assets_validate_lineage_activity(payload: FixedAssetsWorkflowInput) -> dict[str, Any]:
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


@activity.defn(name="fixed_assets_finalize_activity")
async def fixed_assets_finalize_activity(payload: FixedAssetsFinalizeInput) -> dict[str, Any]:
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
