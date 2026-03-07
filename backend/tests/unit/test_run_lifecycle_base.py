from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from financeops.core.exceptions import ValidationError
from financeops.db.base import FinancialBase
from financeops.services.accounting_common.run_lifecycle import (
    append_event,
    create_run_header,
    derive_latest_status,
    validate_lineage_before_finalize,
)
from financeops.services.accounting_common.run_validation import LineageValidationResult


class LifecycleTestRun(FinancialBase):
    __tablename__ = "acct_common_test_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_acct_common_test_signature"),
    )

    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LifecycleTestRunEvent(FinancialBase):
    __tablename__ = "acct_common_test_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_acct_common_test_seq"),
        UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_acct_common_test_idempotent",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("acct_common_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


async def _ensure_test_tables(session: AsyncSession) -> None:
    conn = await session.connection()
    await conn.run_sync(LifecycleTestRun.__table__.create, checkfirst=True)
    await conn.run_sync(LifecycleTestRunEvent.__table__.create, checkfirst=True)


@pytest.mark.asyncio
async def test_create_run_header_is_idempotent(async_session: AsyncSession) -> None:
    await _ensure_test_tables(async_session)

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000001111")
    initiated_by = uuid.UUID("00000000-0000-0000-0000-000000001112")
    payload = {"period_year": 2026, "period_month": 3, "entities": ["a", "b"]}

    first = await create_run_header(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload=payload,
        workflow_id="test-workflow-1",
        correlation_id="corr-acct-common",
        audit_namespace="accounting_common_test",
    )
    second = await create_run_header(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload=payload,
        workflow_id="test-workflow-1",
        correlation_id="corr-acct-common",
        audit_namespace="accounting_common_test",
    )

    assert first.created_new is True
    assert second.created_new is False
    assert first.run_id == second.run_id
    assert second.status == "accepted"


@pytest.mark.asyncio
async def test_append_event_and_derive_latest_status(async_session: AsyncSession) -> None:
    await _ensure_test_tables(async_session)

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000001121")
    initiated_by = uuid.UUID("00000000-0000-0000-0000-000000001122")
    run = await create_run_header(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload={"key": "value"},
        workflow_id="test-workflow-2",
        correlation_id="corr-acct-common-2",
        audit_namespace="accounting_common_test",
    )

    running_event = await append_event(
        async_session,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        run_id=run.run_id,
        user_id=initiated_by,
        event_type="running",
        idempotency_key="stage-running",
        metadata_json={"phase": "running"},
        correlation_id="corr-acct-common-2",
        audit_namespace="accounting_common_test",
    )
    completed_event = await append_event(
        async_session,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        run_id=run.run_id,
        user_id=initiated_by,
        event_type="completed",
        idempotency_key="terminal:completed",
        metadata_json={"result_count": 2},
        correlation_id="corr-acct-common-2",
        audit_namespace="accounting_common_test",
    )

    latest = await derive_latest_status(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        run_id=run.run_id,
    )

    assert running_event.event_seq == 2
    assert completed_event.event_seq == 3
    assert latest.status == "completed"
    assert latest.event_seq == 3
    assert latest.metadata == {"result_count": 2}


@pytest.mark.asyncio
async def test_validate_lineage_before_finalize_appends_failed_event(async_session: AsyncSession) -> None:
    await _ensure_test_tables(async_session)

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000001131")
    initiated_by = uuid.UUID("00000000-0000-0000-0000-000000001132")
    run = await create_run_header(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload={"key": "value"},
        workflow_id="test-workflow-3",
        correlation_id="corr-acct-common-3",
        audit_namespace="accounting_common_test",
    )

    async def _broken_lineage() -> LineageValidationResult:
        return LineageValidationResult(
            is_complete=False,
            details={"missing_chain_links": 1},
        )

    with pytest.raises(ValidationError):
        await validate_lineage_before_finalize(
            async_session,
            event_model=LifecycleTestRunEvent,
            tenant_id=tenant_id,
            run_id=run.run_id,
            user_id=initiated_by,
            correlation_id="corr-acct-common-3",
            audit_namespace="accounting_common_test",
            lineage_validator=_broken_lineage,
        )

    latest = await derive_latest_status(
        async_session,
        run_model=LifecycleTestRun,
        event_model=LifecycleTestRunEvent,
        tenant_id=tenant_id,
        run_id=run.run_id,
    )

    assert latest.status == "failed"
    assert latest.metadata is not None
    assert latest.metadata["error_code"] == "LINEAGE_INCOMPLETE"
