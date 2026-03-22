from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class MonthEndCloseInput:
    tenant_id: str
    period: str


@dataclass(frozen=True)
class MonthEndCloseResult:
    status: str
    period: str
    steps_completed: list[str]
    steps_failed: list[str]
    board_pack_id: str | None


@workflow.defn
class MonthEndCloseWorkflow:
    """
    Durable month-end close workflow with retries per activity.
    """

    @workflow.run
    async def run(self, input: MonthEndCloseInput) -> MonthEndCloseResult:
        steps_completed: list[str] = []
        steps_failed: list[str] = []
        board_pack_id: str | None = None

        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
        )

        async def _run_step(
            *,
            step_name: str,
            activity_name: str,
            timeout: timedelta,
            capture_board_pack: bool = False,
        ) -> None:
            nonlocal board_pack_id
            try:
                result = await workflow.execute_activity(
                    activity_name,
                    args=[input.tenant_id, input.period],
                    start_to_close_timeout=timeout,
                    retry_policy=retry_policy,
                )
                steps_completed.append(step_name)
                if capture_board_pack and isinstance(result, dict):
                    raw_id = result.get("board_pack_id")
                    board_pack_id = str(raw_id) if raw_id else None
            except Exception as exc:
                steps_failed.append(f"{step_name}: {str(exc)[:100]}")

        await _run_step(
            step_name="erp_sync",
            activity_name="sync_erp_data",
            timeout=timedelta(minutes=30),
        )
        await _run_step(
            step_name="gl_reconciliation",
            activity_name="run_gl_reconciliation",
            timeout=timedelta(minutes=20),
        )
        await _run_step(
            step_name="consolidation",
            activity_name="run_consolidation",
            timeout=timedelta(minutes=20),
        )
        await _run_step(
            step_name="mis_recompute",
            activity_name="recompute_mis",
            timeout=timedelta(minutes=10),
        )
        await _run_step(
            step_name="anomaly_detection",
            activity_name="run_anomaly_detection",
            timeout=timedelta(minutes=15),
        )
        await _run_step(
            step_name="board_pack",
            activity_name="generate_board_pack",
            timeout=timedelta(minutes=15),
            capture_board_pack=True,
        )

        await workflow.execute_activity(
            "notify_completion",
            args=[
                input.tenant_id,
                input.period,
                {"completed": steps_completed, "failed": steps_failed},
            ],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        status = "completed" if not steps_failed else "partial"
        return MonthEndCloseResult(
            status=status,
            period=input.period,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            board_pack_id=board_pack_id,
        )

