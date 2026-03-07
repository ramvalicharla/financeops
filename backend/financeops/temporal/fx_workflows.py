from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class FxFetchWorkflowInput:
    tenant_id: str
    requested_by: str
    correlation_id: str
    base_currency: str
    quote_currency: str
    rate_date: str | None


@dataclass(frozen=True)
class FxMonthEndApplyWorkflowInput:
    tenant_id: str
    user_id: str
    correlation_id: str
    period_year: int
    period_month: int
    base_currency: str
    quote_currency: str
    lines: list[dict[str, Any]]
    approval_reason: str


_DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    non_retryable_error_types=["ValidationError"],
)


@workflow.defn
class FxFetchWorkflow:
    @workflow.run
    async def run(self, payload: FxFetchWorkflowInput) -> dict[str, Any]:
        return await workflow.execute_activity(
            "fx_fetch_activity",
            payload,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=_DEFAULT_RETRY_POLICY,
        )


@workflow.defn
class FxMonthEndApplyWorkflow:
    @workflow.run
    async def run(self, payload: FxMonthEndApplyWorkflowInput) -> dict[str, Any]:
        return await workflow.execute_activity(
            "fx_month_end_apply_activity",
            payload,
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
