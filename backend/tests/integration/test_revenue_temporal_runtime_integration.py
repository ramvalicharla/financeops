from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
get_temporal_client = pytest.importorskip("financeops.temporal.client").get_temporal_client

from financeops.temporal.revenue_workflows import (  # noqa: E402
    RevenueRecognitionWorkflow,
    RevenueRecognitionWorkflowInput,
)


@activity.defn(name="revenue_mark_running_activity")
async def _runtime_stub_mark_running(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"event_type": "running", "event_seq": 2, "run_id": payload.run_id}


@activity.defn(name="revenue_load_contracts_and_obligations_activity")
async def _runtime_stub_load(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"contract_count": 1, "obligation_count": 1, "line_item_count": 1, "run_id": payload.run_id}


@activity.defn(name="revenue_allocate_contract_value_activity")
async def _runtime_stub_allocate(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"allocation_count": "1", "total_allocated_contract_currency": "100.000000", "run_id": payload.run_id}


@activity.defn(name="revenue_generate_revenue_schedule_activity")
async def _runtime_stub_schedule(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"schedule_count": 1, "adjustment_count": 0, "run_id": payload.run_id}


@activity.defn(name="revenue_build_journal_preview_activity")
async def _runtime_stub_journal(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"journal_count": 1, "run_id": payload.run_id}


@activity.defn(name="revenue_validate_lineage_activity")
async def _runtime_stub_lineage(payload: RevenueRecognitionWorkflowInput) -> dict:
    return {"lineage_is_complete": True, "details": {}, "run_id": payload.run_id}


@activity.defn(name="revenue_finalize_activity")
async def _runtime_stub_finalize(payload) -> dict:  # type: ignore[no-untyped-def]
    if isinstance(payload, dict):
        event_type = payload.get("event_type", "completed")
        metadata = payload.get("metadata_json", {})
    else:
        event_type = getattr(payload, "event_type", "completed")
        metadata = getattr(payload, "metadata_json", {})
    return {"event_type": event_type, "event_seq": 3, "metadata": metadata}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_revenue_workflow_is_served_by_runtime_worker() -> None:
    try:
        client = await get_temporal_client()
    except Exception as exc:
        pytest.skip(f"Temporal service unavailable: {exc}")

    task_queue = f"financeops-revenue-{uuid.uuid4()}"
    workflow_id = f"financeops-revenue-{uuid.uuid4()}"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[RevenueRecognitionWorkflow],
        activities=[
            _runtime_stub_mark_running,
            _runtime_stub_load,
            _runtime_stub_allocate,
            _runtime_stub_schedule,
            _runtime_stub_journal,
            _runtime_stub_lineage,
            _runtime_stub_finalize,
        ],
    ):
        result = await client.execute_workflow(
            RevenueRecognitionWorkflow.run,
            RevenueRecognitionWorkflowInput(
                run_id="00000000-0000-0000-0000-000000000971",
                tenant_id="00000000-0000-0000-0000-000000000972",
                correlation_id="corr-revenue-runtime",
                requested_by="00000000-0000-0000-0000-000000000973",
                config_hash="cfg-runtime",
            ),
            id=workflow_id,
            task_queue=task_queue,
            run_timeout=timedelta(seconds=30),
        )

    assert result["status"] == "completed"
    assert result["lineage_is_complete"] is True
