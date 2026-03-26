from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

activity = pytest.importorskip("temporalio.activity")
Worker = pytest.importorskip("temporalio.worker").Worker
WorkflowEnvironment = pytest.importorskip("temporalio.testing").WorkflowEnvironment

from financeops.temporal.fx_workflows import FxFetchWorkflow, FxFetchWorkflowInput  # noqa: E402


@activity.defn(name="fx_fetch_activity")
async def _runtime_stub_fx_fetch_activity(payload: FxFetchWorkflowInput) -> dict:
    return {
        "fetch_run_id": "runtime-stub-fetch",
        "status": "success",
        "base_currency": payload.base_currency,
        "quote_currency": payload.quote_currency,
        "rate_date": payload.rate_date or "2026-03-06",
        "selected_rate": "83.100000",
        "selected_source": "provider_consensus",
        "selection_method": "median_of_available_provider_quotes",
        "fallback_used": False,
        "providers": [],
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fx_fetch_workflow_is_served_by_runtime_worker():
    task_queue = f"financeops-fx-fetch-{uuid.uuid4()}"
    workflow_id = f"financeops-fx-fetch-{uuid.uuid4()}"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FxFetchWorkflow],
            activities=[_runtime_stub_fx_fetch_activity],
        ):
            result = await env.client.execute_workflow(
                FxFetchWorkflow.run,
                FxFetchWorkflowInput(
                    tenant_id="00000000-0000-0000-0000-000000000001",
                    requested_by="00000000-0000-0000-0000-000000000001",
                    correlation_id="corr-runtime-fx",
                    base_currency="USD",
                    quote_currency="INR",
                    rate_date="2026-03-06",
                ),
                id=workflow_id,
                task_queue=task_queue,
                run_timeout=timedelta(seconds=20),
            )
    assert result["status"] == "success"
