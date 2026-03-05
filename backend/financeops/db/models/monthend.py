from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase, UUIDBase, utc_now


class MonthEndChecklist(FinancialBase):
    """
    Month-end closing checklist for a period/entity — INSERT ONLY.
    Creating a new checklist for the same period creates a new record (supersedes old).
    """
    __tablename__ = "monthend_checklists"
    __table_args__ = (
        Index("idx_monthend_cl_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_monthend_cl_entity", "tenant_id", "entity_name"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # status: open / in_progress / closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MonthEndTask(UUIDBase):
    """
    Individual task within a month-end checklist.
    Uses UUIDBase (mutable) — status is updated in place since tasks are
    operational workflow records, not immutable financial records.
    """
    __tablename__ = "monthend_tasks"
    __table_args__ = (
        Index("idx_monthend_tasks_checklist", "checklist_id"),
        Index("idx_monthend_tasks_status", "checklist_id", "status"),
    )

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monthend_checklists.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # task_category: reconciliation / approval / reporting / system / other
    task_category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # priority: high / medium / low
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # status: pending / in_progress / completed / skipped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
