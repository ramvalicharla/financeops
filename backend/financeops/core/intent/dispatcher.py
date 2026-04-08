from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.intent.enums import JobRunnerType, JobStatus
from financeops.core.intent.executors import MutationExecutorRegistry
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobDispatcher:
    def __init__(self, executors: MutationExecutorRegistry | None = None) -> None:
        self._executors = executors or MutationExecutorRegistry()

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
            max_retries=0,
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
    ) -> dict[str, object]:
        executor = self._executors.resolve(intent.intent_type)
        job.status = JobStatus.RUNNING.value
        job.started_at = _utcnow()
        await db.flush()

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

        job.status = JobStatus.SUCCEEDED.value
        job.finished_at = _utcnow()
        await db.flush()
        return result.record_refs
