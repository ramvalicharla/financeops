from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class ConsolidationWorkflowInput:
    run_id: str
    tenant_id: str
    correlation_id: str
    requested_by: str
    config_hash: str


@dataclass(frozen=True)
class ConsolidationFinalizeInput:
    run_id: str
    tenant_id: str
    correlation_id: str
    requested_by: str
    config_hash: str
    event_type: str
    metadata_json: dict[str, Any] | None


_DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
    non_retryable_error_types=["ValidationError"],
)


@workflow.defn
class ConsolidationWorkflow:
    @workflow.run
    async def run(self, payload: ConsolidationWorkflowInput) -> dict[str, Any]:
        try:
            await workflow.execute_activity(
                "consolidation_mark_running_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            await workflow.execute_activity(
                "consolidation_prepare_entities_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            await workflow.execute_activity(
                "consolidation_apply_fx_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            await workflow.execute_activity(
                "consolidation_match_ic_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            await workflow.execute_activity(
                "consolidation_compute_eliminations_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            aggregate_result = await workflow.execute_activity(
                "consolidation_aggregate_results_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            terminal = (
                "completed_with_unexplained"
                if int(aggregate_result.get("unexplained_count", 0)) > 0
                else "completed"
            )
            await workflow.execute_activity(
                "consolidation_finalize_activity",
                ConsolidationFinalizeInput(
                    run_id=payload.run_id,
                    tenant_id=payload.tenant_id,
                    correlation_id=payload.correlation_id,
                    requested_by=payload.requested_by,
                    config_hash=payload.config_hash,
                    event_type=terminal,
                    metadata_json=aggregate_result,
                ),
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            return {"run_id": payload.run_id, "status": terminal, **aggregate_result}
        except Exception as exc:
            await workflow.execute_activity(
                "consolidation_finalize_activity",
                ConsolidationFinalizeInput(
                    run_id=payload.run_id,
                    tenant_id=payload.tenant_id,
                    correlation_id=payload.correlation_id,
                    requested_by=payload.requested_by,
                    config_hash=payload.config_hash,
                    event_type="failed",
                    metadata_json={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                ),
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            raise
