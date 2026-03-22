from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
get_temporal_client = pytest.importorskip(
    "financeops.temporal.client"
).get_temporal_client

from financeops.temporal.consolidation_workflows import (  # noqa: E402
    ConsolidationFinalizeInput,
    ConsolidationWorkflow,
    ConsolidationWorkflowInput,
)


@activity.defn(name="consolidation_mark_running_activity")
async def _stub_mark_running(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {"event_seq": 2, "event_type": "running"}


@activity.defn(name="consolidation_prepare_entities_activity")
async def _stub_prepare_entities(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {"entity_count": 3}


@activity.defn(name="consolidation_apply_fx_activity")
async def _stub_apply_fx(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {"line_item_count": 12}


@activity.defn(name="consolidation_match_ic_activity")
async def _stub_match_ic(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {"intercompany_pair_count": 2}


@activity.defn(name="consolidation_compute_eliminations_activity")
async def _stub_compute_eliminations(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {"elimination_count": 2}


@activity.defn(name="consolidation_aggregate_results_activity")
async def _stub_aggregate(payload: ConsolidationWorkflowInput) -> dict:
    del payload
    return {
        "result_count": 4,
        "unexplained_count": 1,
        "total_consolidated_amount_parent": "100.000000",
        "total_fx_impact_parent": "2.500000",
    }


@activity.defn(name="consolidation_finalize_activity")
async def _stub_finalize(payload: ConsolidationFinalizeInput) -> dict:
    if isinstance(payload, dict):
        event_type = payload.get("event_type", "completed")
        metadata = payload.get("metadata_json", {})
    else:
        event_type = getattr(payload, "event_type", "completed")
        metadata = getattr(payload, "metadata_json", {})
    return {
        "event_type": event_type,
        "event_seq": 9,
        "metadata": metadata,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consolidation_workflow_is_served_by_runtime_worker() -> None:
    try:
        client = await get_temporal_client()
    except Exception as exc:
        pytest.skip(f"Temporal service unavailable: {exc}")

    task_queue = f"financeops-consolidation-{uuid.uuid4()}"
    workflow_id = f"financeops-consolidation-{uuid.uuid4()}"
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ConsolidationWorkflow],
        activities=[
            _stub_mark_running,
            _stub_prepare_entities,
            _stub_apply_fx,
            _stub_match_ic,
            _stub_compute_eliminations,
            _stub_aggregate,
            _stub_finalize,
        ],
    ):
        result = await client.execute_workflow(
            ConsolidationWorkflow.run,
            ConsolidationWorkflowInput(
                run_id="00000000-0000-0000-0000-000000000001",
                tenant_id="00000000-0000-0000-0000-000000000001",
                correlation_id="corr-runtime-consol",
                requested_by="00000000-0000-0000-0000-000000000001",
                config_hash="cfg-hash",
            ),
            id=workflow_id,
            task_queue=task_queue,
            run_timeout=timedelta(seconds=25),
        )

    assert result["status"] == "completed_with_unexplained"
    assert result["unexplained_count"] == 1
