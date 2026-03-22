from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from financeops.workflows.month_end_close.workflow import (
    MonthEndCloseInput,
    MonthEndCloseWorkflow,
)

temporal_testing = pytest.importorskip("temporalio.testing")
temporal_worker = pytest.importorskip("temporalio.worker")
temporal_activity = pytest.importorskip("temporalio.activity")
temporal_exceptions = pytest.importorskip("temporalio.exceptions")
temporal_client = pytest.importorskip("temporalio.client")

WorkflowEnvironment = temporal_testing.WorkflowEnvironment
Worker = temporal_worker.Worker
WorkflowAlreadyStartedError = temporal_exceptions.WorkflowAlreadyStartedError
Client = temporal_client.Client
activity = temporal_activity


@activity.defn(name="sync_erp_data")
async def _sync_erp_data(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"synced_connectors": 2, "records": 100}


@activity.defn(name="run_gl_reconciliation")
async def _run_gl_reconciliation(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"breaks": 0, "entities": 2}


@activity.defn(name="run_consolidation")
async def _run_consolidation(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"entities_consolidated": 2}


@activity.defn(name="recompute_mis")
async def _recompute_mis(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"lines_updated": 120}


@activity.defn(name="run_anomaly_detection")
async def _run_anomaly_detection(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"anomalies_detected": 3}


@activity.defn(name="generate_board_pack")
async def _generate_board_pack(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    return {"board_pack_id": str(uuid4())}


@activity.defn(name="notify_completion")
async def _notify_completion(tenant_id: str, period: str, results: dict) -> None:
    _ = tenant_id, period, results


@activity.defn(name="run_gl_reconciliation")
async def _run_gl_reconciliation_fail(tenant_id: str, period: str) -> dict:
    _ = tenant_id, period
    raise RuntimeError("reconciliation exploded")


def _all_success_activities() -> list:
    return [
        _sync_erp_data,
        _run_gl_reconciliation,
        _run_consolidation,
        _recompute_mis,
        _run_anomaly_detection,
        _generate_board_pack,
        _notify_completion,
    ]


@pytest.mark.asyncio
async def test_month_end_close_workflow_completes_all_steps() -> None:
    """All 6 steps complete successfully in happy path."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-month-end-close-success",
            workflows=[MonthEndCloseWorkflow],
            activities=_all_success_activities(),
        ):
            result = await env.client.execute_workflow(
                MonthEndCloseWorkflow.run,
                MonthEndCloseInput(tenant_id=str(uuid4()), period="2025-03"),
                id="test-close-success",
                task_queue="test-month-end-close-success",
            )
    assert result.status == "completed"
    assert len(result.steps_completed) == 6
    assert len(result.steps_failed) == 0


@pytest.mark.asyncio
async def test_month_end_close_continues_after_step_failure() -> None:
    """Workflow continues to remaining steps when one step fails."""
    activities = [
        _sync_erp_data,
        _run_gl_reconciliation_fail,
        _run_consolidation,
        _recompute_mis,
        _run_anomaly_detection,
        _generate_board_pack,
        _notify_completion,
    ]
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-month-end-close-partial",
            workflows=[MonthEndCloseWorkflow],
            activities=activities,
        ):
            result = await env.client.execute_workflow(
                MonthEndCloseWorkflow.run,
                MonthEndCloseInput(tenant_id=str(uuid4()), period="2025-03"),
                id="test-close-partial",
                task_queue="test-month-end-close-partial",
            )
    assert result.status == "partial"
    assert any(step.startswith("gl_reconciliation:") for step in result.steps_failed)
    assert "mis_recompute" in result.steps_completed


@pytest.mark.asyncio
async def test_month_end_close_workflow_id_is_idempotent() -> None:
    """Running close twice for same tenant+period uses same workflow id semantics."""
    tenant_id = str(uuid4())
    period = "2025-03"
    workflow_id = f"month-end-close-{tenant_id}-{period}"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-month-end-close-idem",
            workflows=[MonthEndCloseWorkflow],
            activities=_all_success_activities(),
        ):
            await env.client.start_workflow(
                MonthEndCloseWorkflow.run,
                MonthEndCloseInput(tenant_id=tenant_id, period=period),
                id=workflow_id,
                task_queue="test-month-end-close-idem",
            )
            with pytest.raises(WorkflowAlreadyStartedError):
                await env.client.start_workflow(
                    MonthEndCloseWorkflow.run,
                    MonthEndCloseInput(tenant_id=tenant_id, period=period),
                    id=workflow_id,
                    task_queue="test-month-end-close-idem",
                )


@pytest.mark.asyncio
async def test_temporal_worker_connects() -> None:
    """Worker connects to Temporal and registers workflows."""
    from financeops.config import settings
    from financeops.workers.temporal_worker import run_worker

    try:
        client = await Client.connect(
            str(settings.TEMPORAL_ADDRESS),
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        await client.workflow_service.get_system_info({})
    except Exception:
        pytest.skip("Temporal not available in this env")

    task = asyncio.create_task(run_worker())
    await asyncio.sleep(0.1)
    assert task.done() is False
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
