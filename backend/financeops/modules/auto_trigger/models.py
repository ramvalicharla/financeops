from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


PIPELINE_RUN_STATUSES: tuple[str, ...] = ("running", "completed", "failed", "partial")
PIPELINE_STEP_NAMES: tuple[str, ...] = (
    "gl_reconciliation",
    "payroll_reconciliation",
    "mis_recomputation",
    "anomaly_detection",
)
PIPELINE_STEP_STATUSES: tuple[str, ...] = ("running", "completed", "failed", "skipped")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed','partial')",
            name="ck_pipeline_runs_status",
        ),
        # Only one non-failed active run per tenant/sync pair.
        # Failed rows remain as immutable history and allow retrigger attempts.
        Index(
            "uq_pipeline_runs_tenant_sync_active",
            "tenant_id",
            "sync_run_id",
            unique=True,
            postgresql_where=text("status <> 'failed'"),
        ),
        Index(
            "idx_pipeline_runs_tenant_triggered_desc",
            "tenant_id",
            text("triggered_at DESC"),
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'running'"),
        default="running",
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class PipelineStepLog(Base):
    __tablename__ = "pipeline_step_logs"
    __table_args__ = (
        CheckConstraint(
            "step_name IN ('gl_reconciliation','payroll_reconciliation','mis_recomputation','anomaly_detection')",
            name="ck_pipeline_step_logs_step_name",
        ),
        CheckConstraint(
            "status IN ('running','completed','failed','skipped')",
            name="ck_pipeline_step_logs_status",
        ),
        Index(
            "idx_pipeline_step_logs_run_started_desc",
            "pipeline_run_id",
            text("started_at DESC"),
        ),
        Index(
            "idx_pipeline_step_logs_tenant_status",
            "tenant_id",
            "status",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'running'"),
        default="running",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
