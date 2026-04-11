from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.dispatcher import JobDispatcher
from financeops.core.intent.enums import IntentStatus, IntentType
from financeops.db.models.intent_pipeline import CanonicalIntent
from financeops.observability.beta_monitoring import (
    record_airlock_status,
    record_api_error,
    record_auth_event,
    record_job_finished,
    reset_monitoring_state_for_tests,
)
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


@pytest.fixture(autouse=True)
def _reset_monitoring_state() -> None:
    reset_monitoring_state_for_tests()


@pytest.mark.asyncio
async def test_dispatcher_failure_emits_structured_job_failure_log(
    async_session: AsyncSession,
    test_user,
    caplog: pytest.LogCaptureFixture,
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
        idempotency_key=f"beta-monitoring-{uuid.uuid4()}",
    )
    async_session.add(intent)
    await async_session.flush()

    dispatcher = JobDispatcher()
    job = await dispatcher.create_job(async_session, intent=intent)
    failing_dispatcher = JobDispatcher(_ExecutorRegistryStub(_FailingExecutor()))

    with caplog.at_level(logging.INFO, logger="financeops.observability.beta_monitoring"):
        with pytest.raises(RuntimeError, match="executor failed"):
            await failing_dispatcher.execute(async_session, intent=intent, job=job)

    job_failed_records = [record for record in caplog.records if getattr(record, "event", None) == "job_failed"]
    assert len(job_failed_records) == 1
    record = job_failed_records[0]
    assert record.intent_id == str(intent.id)
    assert record.entity_id == str(intent.entity_id)
    assert record.details["status"] == "failed"
    assert record.details["error"] == "executor failed"


def test_airlock_rejection_emits_structured_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    file_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    with caplog.at_level(logging.INFO, logger="financeops.observability.beta_monitoring"):
        record_airlock_status(
            file_id=file_id,
            entity_id=entity_id,
            status="rejected",
            validation_results=[{"guard_code": "malware_scan", "result": "FAIL"}],
            reason="malware_scan failed",
            source_type="coa_upload",
        )

    rejected = [record for record in caplog.records if getattr(record, "event", None) == "airlock_rejected"]
    assert len(rejected) == 1
    record = rejected[0]
    assert record.entity_id == str(entity_id)
    assert record.details["status"] == "rejected"
    assert record.details["reason"] == "malware_scan failed"
    assert record.details["validation_results"][0]["guard_code"] == "malware_scan"


def test_alert_conditions_emit_warning_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="financeops.observability.beta_monitoring"):
        for _ in range(4):
            record_job_finished(
                job_id=uuid.uuid4(),
                intent_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                status="failed",
                duration_ms=125.0,
                error="boom",
                retry_count=1,
                max_retries=3,
            )
        for _ in range(5):
            record_api_error(
                method="GET",
                path="/api/v1/platform/control-plane/context",
                status_code=500,
                error_type="RuntimeError",
                duration_ms=55.0,
            )
        for _ in range(5):
            record_auth_event(
                event="auth_login_failed",
                outcome="failure",
                email="ops@example.com",
                failure_type="password_mismatch",
            )

    events = {getattr(record, "event", None) for record in caplog.records}
    assert "job_failure_streak_alert" in events
    assert "api_error_rate_spike" in events
    assert "auth_failure_spike" in events


def test_long_running_job_emits_warning_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="financeops.observability.beta_monitoring"):
        record_job_finished(
            job_id=uuid.uuid4(),
            intent_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            status="success",
            duration_ms=31_000.0,
            retry_count=0,
            max_retries=3,
        )

    assert any(
        getattr(record, "event", None) == "job_duration_exceeded" for record in caplog.records
    )
