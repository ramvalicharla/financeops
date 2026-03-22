from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
get_temporal_client = pytest.importorskip("financeops.temporal.client").get_temporal_client

from financeops.temporal.lease_workflows import (  # noqa: E402
    LeaseAccountingWorkflow,
    LeaseAccountingWorkflowInput,
)


@activity.defn(name="lease_mark_running_activity")
async def _runtime_stub_mark_running(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"event_type": "running", "event_seq": 2, "run_id": payload.run_id}


@activity.defn(name="lease_load_leases_and_payments_activity")
async def _runtime_stub_load(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"lease_count": 1, "payment_count": 1, "run_id": payload.run_id}


@activity.defn(name="lease_build_payment_timeline_activity")
async def _runtime_stub_timeline(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"timeline_count": 1, "run_id": payload.run_id}


@activity.defn(name="lease_calculate_present_value_activity")
async def _runtime_stub_pv(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"lease_count": "1", "total_present_value_reporting_currency": "100.000000", "run_id": payload.run_id}


@activity.defn(name="lease_generate_liability_schedule_activity")
async def _runtime_stub_liability(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"liability_count": 1, "modification_count": 0, "run_id": payload.run_id}


@activity.defn(name="lease_generate_rou_schedule_activity")
async def _runtime_stub_rou(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"rou_count": 1, "run_id": payload.run_id}


@activity.defn(name="lease_build_journal_preview_activity")
async def _runtime_stub_journal(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"journal_count": 2, "run_id": payload.run_id}


@activity.defn(name="lease_validate_lineage_activity")
async def _runtime_stub_lineage(payload: LeaseAccountingWorkflowInput) -> dict:
    return {"lineage_is_complete": True, "details": {}, "run_id": payload.run_id}


@activity.defn(name="lease_finalize_activity")
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
async def test_lease_workflow_is_served_by_runtime_worker() -> None:
    try:
        client = await get_temporal_client()
    except Exception as exc:
        pytest.skip(f"Temporal service unavailable: {exc}")

    task_queue = f"financeops-lease-{uuid.uuid4()}"
    workflow_id = f"financeops-lease-{uuid.uuid4()}"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[LeaseAccountingWorkflow],
        activities=[
            _runtime_stub_mark_running,
            _runtime_stub_load,
            _runtime_stub_timeline,
            _runtime_stub_pv,
            _runtime_stub_liability,
            _runtime_stub_rou,
            _runtime_stub_journal,
            _runtime_stub_lineage,
            _runtime_stub_finalize,
        ],
    ):
        result = await client.execute_workflow(
            LeaseAccountingWorkflow.run,
            LeaseAccountingWorkflowInput(
                run_id="00000000-0000-0000-0000-000000001371",
                tenant_id="00000000-0000-0000-0000-000000001372",
                correlation_id="corr-lease-runtime",
                requested_by="00000000-0000-0000-0000-000000001373",
                config_hash="cfg-lease-runtime",
            ),
            id=workflow_id,
            task_queue=task_queue,
            run_timeout=timedelta(seconds=30),
        )

    assert result["status"] == "completed"
    assert result["lineage_is_complete"] is True
