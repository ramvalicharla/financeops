from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
WorkflowEnvironment = pytest.importorskip("temporalio.testing").WorkflowEnvironment

from financeops.temporal.prepaid_workflows import (  # noqa: E402
    PrepaidAmortizationWorkflow,
    PrepaidAmortizationWorkflowInput,
    PrepaidFinalizeInput,
)


@activity.defn(name="prepaid_mark_running_activity")
async def _runtime_stub_mark_running(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"event_type": "running", "event_seq": 2, "run_id": payload.run_id}


@activity.defn(name="prepaid_load_prepaids_activity")
async def _runtime_stub_load(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"prepaid_count": 1, "run_id": payload.run_id}


@activity.defn(name="prepaid_resolve_amortization_pattern_activity")
async def _runtime_stub_pattern(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"pattern_count": 1, "period_count": 3, "run_id": payload.run_id}


@activity.defn(name="prepaid_generate_amortization_schedule_activity")
async def _runtime_stub_schedule(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"schedule_count": 3, "adjustment_count": 0, "run_id": payload.run_id}


@activity.defn(name="prepaid_build_journal_preview_activity")
async def _runtime_stub_journal(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"journal_count": 3, "run_id": payload.run_id}


@activity.defn(name="prepaid_validate_lineage_activity")
async def _runtime_stub_lineage(payload: PrepaidAmortizationWorkflowInput) -> dict:
    return {"lineage_is_complete": True, "details": {}, "run_id": payload.run_id}


@activity.defn(name="prepaid_finalize_activity")
async def _runtime_stub_finalize(payload: PrepaidFinalizeInput) -> dict:
    if isinstance(payload, dict):
        event_type = payload.get("event_type", "completed")
        metadata = payload.get("metadata_json", {})
    else:
        event_type = getattr(payload, "event_type", "completed")
        metadata = getattr(payload, "metadata_json", {})
    return {"event_type": event_type, "event_seq": 3, "metadata": metadata}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_prepaid_workflow_is_served_by_runtime_worker() -> None:
    task_queue = f"financeops-prepaid-{uuid.uuid4()}"
    workflow_id = f"financeops-prepaid-{uuid.uuid4()}"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[PrepaidAmortizationWorkflow],
            activities=[
                _runtime_stub_mark_running,
                _runtime_stub_load,
                _runtime_stub_pattern,
                _runtime_stub_schedule,
                _runtime_stub_journal,
                _runtime_stub_lineage,
                _runtime_stub_finalize,
            ],
        ):
            result = await env.client.execute_workflow(
                PrepaidAmortizationWorkflow.run,
                PrepaidAmortizationWorkflowInput(
                    run_id="00000000-0000-0000-0000-000000012901",
                    tenant_id="00000000-0000-0000-0000-000000012902",
                    correlation_id="corr-prepaid-runtime",
                    requested_by="00000000-0000-0000-0000-000000012903",
                    config_hash="cfg-prepaid-runtime",
                ),
                id=workflow_id,
                task_queue=task_queue,
                run_timeout=timedelta(seconds=30),
            )

    assert result["status"] == "completed"
    assert result["lineage_is_complete"] is True
