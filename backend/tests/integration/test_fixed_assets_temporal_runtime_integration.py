from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
WorkflowEnvironment = pytest.importorskip("temporalio.testing").WorkflowEnvironment

from financeops.temporal.fixed_assets_workflows import (  # noqa: E402
    FixedAssetsFinalizeInput,
    FixedAssetsWorkflow,
    FixedAssetsWorkflowInput,
)


@activity.defn(name="fixed_assets_mark_running_activity")
async def _runtime_stub_mark_running(payload: FixedAssetsWorkflowInput) -> dict:
    return {"event_type": "running", "event_seq": 2, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_load_assets_activity")
async def _runtime_stub_load(payload: FixedAssetsWorkflowInput) -> dict:
    return {"asset_count": 1, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_generate_depreciation_schedule_activity")
async def _runtime_stub_schedule(payload: FixedAssetsWorkflowInput) -> dict:
    return {"schedule_count": 3, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_apply_impairment_disposal_activity")
async def _runtime_stub_events(payload: FixedAssetsWorkflowInput) -> dict:
    return {"impairment_count": 0, "disposal_count": 0, "regenerated_schedule_count": 0, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_build_journal_preview_activity")
async def _runtime_stub_journal(payload: FixedAssetsWorkflowInput) -> dict:
    return {"journal_count": 3, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_validate_lineage_activity")
async def _runtime_stub_lineage(payload: FixedAssetsWorkflowInput) -> dict:
    return {"lineage_is_complete": True, "details": {}, "run_id": payload.run_id}


@activity.defn(name="fixed_assets_finalize_activity")
async def _runtime_stub_finalize(payload: FixedAssetsFinalizeInput) -> dict:
    if isinstance(payload, dict):
        event_type = payload.get("event_type", "completed")
        metadata = payload.get("metadata_json", {})
    else:
        event_type = getattr(payload, "event_type", "completed")
        metadata = getattr(payload, "metadata_json", {})
    return {"event_type": event_type, "event_seq": 3, "metadata": metadata}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fixed_assets_workflow_is_served_by_runtime_worker() -> None:
    task_queue = f"financeops-far-{uuid.uuid4()}"
    workflow_id = f"financeops-far-{uuid.uuid4()}"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FixedAssetsWorkflow],
            activities=[
                _runtime_stub_mark_running,
                _runtime_stub_load,
                _runtime_stub_schedule,
                _runtime_stub_events,
                _runtime_stub_journal,
                _runtime_stub_lineage,
                _runtime_stub_finalize,
            ],
        ):
            result = await env.client.execute_workflow(
                FixedAssetsWorkflow.run,
                FixedAssetsWorkflowInput(
                    run_id="00000000-0000-0000-0000-00000000f901",
                    tenant_id="00000000-0000-0000-0000-00000000f902",
                    correlation_id="corr-far-runtime",
                    requested_by="00000000-0000-0000-0000-00000000f903",
                    config_hash="cfg-far-runtime",
                ),
                id=workflow_id,
                task_queue=task_queue,
                run_timeout=timedelta(seconds=30),
            )

    assert result["status"] == "completed"
    assert result["lineage_is_complete"] is True
