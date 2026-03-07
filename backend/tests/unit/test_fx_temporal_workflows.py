from __future__ import annotations

import pytest

activity_mod = pytest.importorskip("temporalio.activity")
testing_mod = pytest.importorskip("temporalio.testing")
worker_mod = pytest.importorskip("temporalio.worker")

from financeops.temporal.fx_workflows import (  # noqa: E402
    FxFetchWorkflow,
    FxFetchWorkflowInput,
    FxMonthEndApplyWorkflow,
    FxMonthEndApplyWorkflowInput,
)

activity = activity_mod
WorkflowEnvironment = testing_mod.WorkflowEnvironment
Worker = worker_mod.Worker


@activity.defn(name="fx_fetch_activity")
async def _stub_fetch_activity(payload: FxFetchWorkflowInput) -> dict:
    return {
        "fetch_run_id": "stub-fetch",
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


@activity.defn(name="fx_month_end_apply_activity")
async def _stub_month_end_activity(payload: FxMonthEndApplyWorkflowInput) -> dict:
    return {
        "period_year": payload.period_year,
        "period_month": payload.period_month,
        "base_currency": payload.base_currency,
        "quote_currency": payload.quote_currency,
        "selected_rate": "83.500000",
        "selected_source": "manual_monthly",
        "lines": [],
        "count": 0,
        "lock_rate_id": "stub-lock",
    }


@pytest.mark.asyncio
async def test_fx_fetch_workflow_runs() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "fx-fetch-workflow-test"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FxFetchWorkflow],
            activities=[_stub_fetch_activity],
        ):
            result = await env.client.execute_workflow(
                FxFetchWorkflow.run,
                FxFetchWorkflowInput(
                    tenant_id="00000000-0000-0000-0000-000000000001",
                    requested_by="00000000-0000-0000-0000-000000000001",
                    correlation_id="corr-wf-fetch",
                    base_currency="USD",
                    quote_currency="INR",
                    rate_date="2026-03-06",
                ),
                id="fx-fetch-workflow-test-id",
                task_queue=task_queue,
            )
            assert result["status"] == "success"


@activity.defn(name="fx_fetch_activity")
async def _stub_degraded_fetch_activity(payload: FxFetchWorkflowInput) -> dict:
    return {
        "fetch_run_id": "stub-fetch-degraded",
        "status": "degraded",
        "base_currency": payload.base_currency,
        "quote_currency": payload.quote_currency,
        "rate_date": payload.rate_date or "2026-03-06",
        "selected_rate": "83.100000",
        "selected_source": "provider_consensus",
        "selection_method": "median_of_available_provider_quotes",
        "fallback_used": False,
        "providers": [
            {"provider": "ecb", "status": "ok", "rate": "83.100000", "rate_date": "2026-03-06", "error": None},
            {"provider": "frankfurter", "status": "ok", "rate": "83.200000", "rate_date": "2026-03-06", "error": None},
            {
                "provider": "open_exchange_rates",
                "status": "error",
                "rate": None,
                "rate_date": None,
                "error": "OPEN_EXCHANGE_RATES_API_KEY not configured",
            },
            {
                "provider": "exchange_rate_api",
                "status": "error",
                "rate": None,
                "rate_date": None,
                "error": "EXCHANGE_RATE_API_KEY not configured",
            },
        ],
    }


@pytest.mark.asyncio
async def test_fx_fetch_workflow_returns_degraded_payload_without_exception() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "fx-fetch-workflow-degraded-test"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FxFetchWorkflow],
            activities=[_stub_degraded_fetch_activity],
        ):
            result = await env.client.execute_workflow(
                FxFetchWorkflow.run,
                FxFetchWorkflowInput(
                    tenant_id="00000000-0000-0000-0000-000000000001",
                    requested_by="00000000-0000-0000-0000-000000000001",
                    correlation_id="corr-wf-fetch-degraded",
                    base_currency="USD",
                    quote_currency="INR",
                    rate_date="2026-03-06",
                ),
                id="fx-fetch-workflow-degraded-test-id",
                task_queue=task_queue,
            )
            assert result["status"] == "degraded"
            assert len(result["providers"]) == 4


@pytest.mark.asyncio
async def test_fx_month_end_apply_workflow_runs() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "fx-month-end-workflow-test"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FxMonthEndApplyWorkflow],
            activities=[_stub_month_end_activity],
        ):
            result = await env.client.execute_workflow(
                FxMonthEndApplyWorkflow.run,
                FxMonthEndApplyWorkflowInput(
                    tenant_id="00000000-0000-0000-0000-000000000001",
                    user_id="00000000-0000-0000-0000-000000000001",
                    correlation_id="corr-wf-month-end",
                    period_year=2026,
                    period_month=3,
                    base_currency="USD",
                    quote_currency="INR",
                    lines=[],
                    approval_reason="approved",
                ),
                id="fx-month-end-workflow-test-id",
                task_queue=task_queue,
            )
            assert result["lock_rate_id"] == "stub-lock"
