from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class LeaseAccountingWorkflowInput:
    run_id: str
    tenant_id: str
    correlation_id: str
    requested_by: str
    config_hash: str


@dataclass(frozen=True)
class LeaseFinalizeInput:
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
class LeaseAccountingWorkflow:
    @workflow.run
    async def run(self, payload: LeaseAccountingWorkflowInput) -> dict[str, Any]:
        try:
            await workflow.execute_activity(
                "lease_mark_running_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            load_result = await workflow.execute_activity(
                "lease_load_leases_and_payments_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            timeline_result = await workflow.execute_activity(
                "lease_build_payment_timeline_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            pv_result = await workflow.execute_activity(
                "lease_calculate_present_value_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            liability_result = await workflow.execute_activity(
                "lease_generate_liability_schedule_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            rou_result = await workflow.execute_activity(
                "lease_generate_rou_schedule_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            journal_result = await workflow.execute_activity(
                "lease_build_journal_preview_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            lineage_result = await workflow.execute_activity(
                "lease_validate_lineage_activity",
                payload,
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )

            metadata = {
                **load_result,
                **timeline_result,
                **pv_result,
                **liability_result,
                **rou_result,
                **journal_result,
                **lineage_result,
            }

            await workflow.execute_activity(
                "lease_finalize_activity",
                LeaseFinalizeInput(
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
            await workflow.execute_activity(
                "lease_finalize_activity",
                LeaseFinalizeInput(
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
