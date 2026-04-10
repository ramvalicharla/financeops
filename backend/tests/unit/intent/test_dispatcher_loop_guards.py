from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.core.intent.enums import JobStatus, IntentStatus, IntentType
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalJob
from financeops.platform.db.models.entities import CpEntity


class _FailingExecutor:
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent):
        del db, intent
        raise RuntimeError("executor failed")


class _ExecutorRegistryStub:
    def __init__(self, executor) -> None:
        self._executor = executor

    def resolve(self, intent_type: str):
        del intent_type
        return self._executor


@pytest.mark.asyncio
async def test_dispatcher_blocks_worker_reentry_for_running_jobs(
    async_session: AsyncSession,
    test_user,
) -> None:
    entity = (
        await async_session.execute(select(CpEntity).where(CpEntity.tenant_id == test_user.tenant_id))
    ).scalar_one()
    intent = CanonicalIntent(
        tenant_id=test_user.tenant_id,
        org_id=entity.organisation_id,
        entity_id=entity.id,
        intent_type=IntentType.CREATE_JOURNAL.value,
        module_key="accounting_layer",
        target_type="journal",
        status=IntentStatus.APPROVED.value,
        requested_by_user_id=test_user.id,
        requested_by_role=test_user.role.value,
        payload_json={},
        idempotency_key=f"dispatcher-running-{uuid.uuid4()}",
    )
    async_session.add(intent)
    await async_session.flush()

    job = CanonicalJob(
        intent_id=intent.id,
        job_type=intent.intent_type,
        status=JobStatus.RUNNING.value,
        runner_type="INLINE",
        queue_name="governed-financial-mutations",
        idempotency_key=intent.idempotency_key,
        retry_count=0,
        max_retries=3,
    )
    async_session.add(job)
    await async_session.flush()

    dispatcher = JobDispatcher(_ExecutorRegistryStub(_FailingExecutor()))

    with pytest.raises(ValidationError, match="already running"):
        await dispatcher.execute(async_session, intent=intent, job=job)


@pytest.mark.asyncio
async def test_dispatcher_marks_failure_once_and_blocks_reexecution(
    async_session: AsyncSession,
    test_user,
) -> None:
    entity = (
        await async_session.execute(select(CpEntity).where(CpEntity.tenant_id == test_user.tenant_id))
    ).scalar_one()
    intent = CanonicalIntent(
        tenant_id=test_user.tenant_id,
        org_id=entity.organisation_id,
        entity_id=entity.id,
        intent_type=IntentType.CREATE_JOURNAL.value,
        module_key="accounting_layer",
        target_type="journal",
        status=IntentStatus.APPROVED.value,
        requested_by_user_id=test_user.id,
        requested_by_role=test_user.role.value,
        payload_json={},
        idempotency_key=f"dispatcher-failed-{uuid.uuid4()}",
    )
    async_session.add(intent)
    await async_session.flush()

    job = CanonicalJob(
        intent_id=intent.id,
        job_type=intent.intent_type,
        status=JobStatus.PENDING.value,
        runner_type="INLINE",
        queue_name="governed-financial-mutations",
        idempotency_key=intent.idempotency_key,
        retry_count=0,
        max_retries=3,
    )
    async_session.add(job)
    await async_session.flush()

    dispatcher = JobDispatcher(_ExecutorRegistryStub(_FailingExecutor()))

    with pytest.raises(RuntimeError, match="executor failed"):
        await dispatcher.execute(async_session, intent=intent, job=job)

    await async_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.retry_count == 1

    with pytest.raises(ValidationError, match="cannot execute from status"):
        await dispatcher.execute(async_session, intent=intent, job=job)
