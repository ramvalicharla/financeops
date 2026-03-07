from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class TenantOnboardingWorkflowInput:
    tenant_id: str
    correlation_id: str
    requested_by: str
    config_hash: str


_DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=8),
    maximum_attempts=3,
    non_retryable_error_types=["ValidationError", "AuthenticationError"],
)


@workflow.defn
class TenantOnboardingWorkflow:
    @workflow.run
    async def run(self, payload: TenantOnboardingWorkflowInput) -> dict:
        await workflow.execute_activity(
            "tenant_onboarding_validate_activity",
            payload,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
        result = await workflow.execute_activity(
            "tenant_onboarding_finalize_activity",
            payload,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
        return {"status": "completed", **result}
