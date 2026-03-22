from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"
    __table_args__ = (
        Index("idx_checklist_templates_tenant", "tenant_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ChecklistTemplateTask(Base):
    __tablename__ = "checklist_template_tasks"
    __table_args__ = (
        CheckConstraint(
            "assigned_role IS NULL OR assigned_role IN ('finance_leader','manager','reviewer','data_entry_gl','data_entry_payroll')",
            name="ck_checklist_template_tasks_assigned_role",
        ),
        CheckConstraint(
            "auto_trigger_event IS NULL OR auto_trigger_event IN ('erp_sync_complete','recon_complete','consolidation_complete','board_pack_generated','anomaly_detection_complete')",
            name="ck_checklist_template_tasks_event",
        ),
        Index("idx_checklist_template_tasks_template_order", "template_id", "order_index"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    days_relative_to_period_end: Mapped[int] = mapped_column(Integer, nullable=False)
    depends_on_task_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    auto_trigger_event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ChecklistRun(Base):
    __tablename__ = "checklist_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_progress','completed','locked')",
            name="ck_checklist_runs_status",
        ),
        UniqueConstraint("tenant_id", "period", name="uq_checklist_runs_tenant_period"),
        Index("idx_checklist_runs_tenant_period", "tenant_id", "period"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'open'"),
        default="open",
    )
    progress_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    target_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ChecklistRunTask(Base):
    __tablename__ = "checklist_run_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started','in_progress','completed','blocked','skipped')",
            name="ck_checklist_run_tasks_status",
        ),
        Index("idx_checklist_run_tasks_run_status", "run_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_template_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_name: Mapped[str] = mapped_column(String(300), nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'not_started'"),
        default="not_started",
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_auto_completed: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    auto_completed_by_event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "ChecklistTemplate",
    "ChecklistTemplateTask",
    "ChecklistRun",
    "ChecklistRunTask",
]

