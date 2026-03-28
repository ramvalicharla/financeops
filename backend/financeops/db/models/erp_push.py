from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import FinancialBase


class PushStatus:
    PUSH_IN_PROGRESS = "PUSH_IN_PROGRESS"
    PUSHED = "PUSHED"
    PUSH_FAILED = "PUSH_FAILED"
    DEAD_LETTER = "DEAD_LETTER"

    ALL = frozenset({PUSH_IN_PROGRESS, PUSHED, PUSH_FAILED, DEAD_LETTER})
    TERMINAL = frozenset({PUSHED, DEAD_LETTER})


class ErrorCategory:
    HARD = "HARD"
    SOFT = "SOFT"


class PushEventType:
    PUSH_INITIATED = "PUSH_INITIATED"
    ERP_API_CALLED = "ERP_API_CALLED"
    ERP_API_SUCCEEDED = "ERP_API_SUCCEEDED"
    ERP_API_FAILED = "ERP_API_FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    DEAD_LETTERED = "DEAD_LETTERED"
    STATUS_POLLED = "STATUS_POLLED"


class ErpPushRun(FinancialBase):
    __tablename__ = "erp_push_runs"
    __table_args__ = (
        Index("ix_erp_push_runs_jv_id", "jv_id"),
        Index("ix_erp_push_runs_idempotency_key", "tenant_id", "idempotency_key"),
        Index("ix_erp_push_runs_status", "tenant_id", "status"),
        Index("ix_erp_push_runs_connection_id", "connection_id"),
        CheckConstraint(
            "status IN ('PUSH_IN_PROGRESS','PUSHED','PUSH_FAILED','DEAD_LETTER')",
            name="ck_erp_push_runs_status",
        ),
        CheckConstraint(
            "error_category IS NULL OR error_category IN ('HARD','SOFT')",
            name="ck_erp_push_runs_error_category",
        ),
    )

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    jv_version: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    external_journal_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    erp_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["ErpPushEvent"]] = relationship(
        "ErpPushEvent",
        foreign_keys="ErpPushEvent.push_run_id",
        lazy="raise",
    )


class ErpPushEvent(FinancialBase):
    __tablename__ = "erp_push_events"
    __table_args__ = (
        Index("ix_erp_push_events_push_run_id", "push_run_id"),
        Index("ix_erp_push_events_jv_id", "jv_id"),
    )

    push_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_push_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ErpPushIdempotencyKey(FinancialBase):
    __tablename__ = "erp_push_idempotency_keys"
    __table_args__ = (
        Index(
            "ix_erp_push_idempotency_keys_lookup",
            "tenant_id",
            "idempotency_key",
            "created_at",
        ),
        Index("ix_erp_push_idempotency_keys_jv_id", "jv_id"),
        CheckConstraint(
            "status IN ('PUSH_IN_PROGRESS','PUSHED','PUSH_FAILED','DEAD_LETTER')",
            name="ck_erp_push_idempotency_keys_status",
        ),
    )

    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    push_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("erp_push_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    external_journal_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
