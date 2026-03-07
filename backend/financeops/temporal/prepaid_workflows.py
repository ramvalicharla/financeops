from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class PrepaidAmortizationWorkflowInput:
    run_id: str
    tenant_id: str
    correlation_id: str
    requested_by: str
    config_hash: str


@dataclass(frozen=True)
class PrepaidFinalizeInput:
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
class PrepaidAmortizationWorkflow:
    @workflow.run
    async def run(self, payload: PrepaidAmortizationWorkflowInput) -> dict[str, Any]:
        try:
            await workflow.execute_activity(
                "prepaid_mark_running_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            load_result = await workflow.execute_activity(
                "prepaid_load_prepaids_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            pattern_result = await workflow.execute_activity(
                "prepaid_resolve_amortization_pattern_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            schedule_result = await workflow.execute_activity(
                "prepaid_generate_amortization_schedule_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            journal_result = await workflow.execute_activity(
                "prepaid_build_journal_preview_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            lineage_result = await workflow.execute_activity(
                "prepaid_validate_lineage_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )

            metadata = {
                **load_result,
                **pattern_result,
                **schedule_result,
                **journal_result,
                **lineage_result,
            }

            await workflow.execute_activity(
                "prepaid_finalize_activity",
                PrepaidFinalizeInput(
                    run_id=payload.run_id,
                    tenant_id=payload.tenant_id,
                    correlation_id=payload.correlation_id,
                    requested_by=payload.requested_by,
                    config_hash=payload.config_hash,
                    event_type="completed",
                    metadata_json=metadata,
                ),
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            return {
                "run_id": payload.run_id,
                "status": "completed",
                **metadata,
            }
        except Exception as exc:
            error_code = str(getattr(exc, "error_code", "WORKFLOW_FAILED"))
            await workflow.execute_activity(
                "prepaid_finalize_activity",
                PrepaidFinalizeInput(
                    run_id=payload.run_id,
                    tenant_id=payload.tenant_id,
                    correlation_id=payload.correlation_id,
                    requested_by=payload.requested_by,
                    config_hash=payload.config_hash,
                    event_type="failed",
                    metadata_json={
                        "error_code": error_code,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                ),
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            raise


# Backward-compatible alias for existing imports.
PrepaidWorkflow = PrepaidAmortizationWorkflow
