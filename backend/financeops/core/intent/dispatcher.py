from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.intent.enums import JobRunnerType, JobStatus
from financeops.core.intent.executors import MutationExecutorRegistry
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_MAX_JOB_RETRIES = 3


class JobDispatcher:
    def __init__(self, executors: MutationExecutorRegistry | None = None) -> None:
        self._executors = executors or MutationExecutorRegistry()

    async def start_temporal_workflow(
        self,
        workflow_run: Any,
        payload: Any,
        *,
        workflow_id: str,
        task_queue: str,
        execution_timeout: Any | None = None,
        run_timeout: Any | None = None,
    ) -> Any:
        from financeops.temporal.client import get_temporal_client

        temporal_client = await get_temporal_client()
        kwargs: dict[str, Any] = {"id": workflow_id, "task_queue": task_queue}
        if execution_timeout is not None:
            kwargs["execution_timeout"] = execution_timeout
        if run_timeout is not None:
            kwargs["run_timeout"] = run_timeout
        return await temporal_client.start_workflow(workflow_run, payload, **kwargs)

    async def execute_temporal_workflow(
        self,
        workflow_run: Any,
        payload: Any,
        *,
        workflow_id: str,
        task_queue: str,
        execution_timeout: Any | None = None,
        run_timeout: Any | None = None,
    ) -> Any:
        from financeops.temporal.client import get_temporal_client

        temporal_client = await get_temporal_client()
        kwargs: dict[str, Any] = {"id": workflow_id, "task_queue": task_queue}
        if execution_timeout is not None:
            kwargs["execution_timeout"] = execution_timeout
        if run_timeout is not None:
            kwargs["run_timeout"] = run_timeout
        return await temporal_client.execute_workflow(workflow_run, payload, **kwargs)

    async def get_temporal_workflow_handle(self, workflow_id: str) -> Any:
        from financeops.temporal.client import get_temporal_client

        temporal_client = await get_temporal_client()
        return temporal_client.get_workflow_handle(workflow_id)

    def enqueue_task(self, task: Any, *args: Any, **kwargs: Any) -> Any:
        return task.delay(*args, **kwargs)

    async def create_job(
        self,
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
    ) -> CanonicalJob:
        job = CanonicalJob(
            id=uuid.uuid4(),
            intent_id=intent.id,
            job_type=intent.intent_type,
            status=JobStatus.PENDING.value,
            runner_type=JobRunnerType.INLINE.value,
            queue_name="governed-financial-mutations",
            idempotency_key=intent.idempotency_key,
            requested_at=_utcnow(),
            retry_count=0,
            max_retries=DEFAULT_MAX_JOB_RETRIES,
        )
        db.add(job)
        await db.flush()
        return job

    async def execute(
        self,
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
        job: CanonicalJob,
    ):
        persisted_job = (
            await db.execute(
                select(CanonicalJob).where(CanonicalJob.id == job.id).with_for_update()
            )
        ).scalar_one()
        if persisted_job.status == JobStatus.RUNNING.value:
            raise ValidationError("Job is already running; worker re-entry blocked.")
        if persisted_job.status != JobStatus.PENDING.value:
            raise ValidationError(
                f"Job cannot execute from status '{persisted_job.status}'."
            )

        executor = self._executors.resolve(intent.intent_type)
        persisted_job.status = JobStatus.RUNNING.value
        persisted_job.started_at = _utcnow()
        await db.flush()

        try:
            with governed_mutation_context(
                MutationContext(
                    intent_id=intent.id,
                    job_id=job.id,
                    actor_user_id=intent.requested_by_user_id,
                    actor_role=intent.requested_by_role,
                    intent_type=intent.intent_type,
                )
            ):
                result = await executor.execute(db, intent=intent)
        except Exception as exc:
            persisted_job.status = JobStatus.FAILED.value
            persisted_job.failed_at = _utcnow()
            persisted_job.error_message = str(exc)[:2000]
            persisted_job.retry_count = min(
                persisted_job.retry_count + 1,
                persisted_job.max_retries,
            )
            await db.flush()
            raise

        persisted_job.status = JobStatus.SUCCEEDED.value
        persisted_job.finished_at = _utcnow()
        await db.flush()
        return result
