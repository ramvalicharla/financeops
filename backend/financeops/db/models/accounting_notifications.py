from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class NotificationType:
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    JV_APPROVED = "JV_APPROVED"
    JV_REJECTED = "JV_REJECTED"
    SLA_BREACH = "SLA_BREACH"
    PUSH_FAILED = "PUSH_FAILED"
    DAILY_DIGEST = "DAILY_DIGEST"
    REMINDER_24H = "REMINDER_24H"
    REMINDER_48H = "REMINDER_48H"

    ALL = frozenset(
        {
            APPROVAL_REQUIRED,
            JV_APPROVED,
            JV_REJECTED,
            SLA_BREACH,
            PUSH_FAILED,
            DAILY_DIGEST,
            REMINDER_24H,
            REMINDER_48H,
        }
    )


class NotificationChannel:
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"

    ALL = frozenset({IN_APP, EMAIL, PUSH})


class ExportType:
    JV_LIFECYCLE = "JV_LIFECYCLE"
    ERP_PUSH = "ERP_PUSH"
    APPROVALS = "APPROVALS"
    AP_AGEING = "AP_AGEING"
    FULL_ACCOUNTING = "FULL_ACCOUNTING"

    ALL = frozenset(
        {
            JV_LIFECYCLE,
            ERP_PUSH,
            APPROVALS,
            AP_AGEING,
            FULL_ACCOUNTING,
        }
    )


class ExportFormat:
    CSV = "CSV"
    PDF = "PDF"

    ALL = frozenset({CSV, PDF})


class AccountingNotificationEvent(FinancialBase):
    __tablename__ = "accounting_notification_events"
    __table_args__ = (
        Index("ix_accounting_notification_events_tenant", "tenant_id"),
        Index("ix_accounting_notification_events_jv_id", "jv_id"),
        Index("ix_accounting_notification_events_recipient", "recipient_user_id"),
    )

    jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=True,
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalReminderRun(FinancialBase):
    __tablename__ = "approval_reminder_runs"
    __table_args__ = (
        Index("ix_approval_reminder_runs_tenant", "tenant_id"),
        Index("ix_approval_reminder_runs_jv_id", "jv_id"),
    )

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reminder_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountingAPAgeingSnapshot(FinancialBase):
    __tablename__ = "accounting_ap_ageing_snapshots"
    __table_args__ = (
        Index("ix_ap_ageing_snapshots_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_ap_ageing_snapshots_snapshot_date", "tenant_id", "snapshot_date"),
        Index("ix_ap_ageing_snapshots_vendor", "vendor_id"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_vendors.id", ondelete="RESTRICT"),
        nullable=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(Integer, nullable=False)

    current_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    overdue_1_30: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    overdue_31_60: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    overdue_61_90: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    overdue_90_plus: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    total_outstanding: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    data_source: Mapped[str] = mapped_column(String(16), nullable=False, default="ERP_PULL")
    connector_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    @property
    def total_overdue(self) -> Decimal:
        return self.overdue_1_30 + self.overdue_31_60 + self.overdue_61_90 + self.overdue_90_plus


class AccountingAuditExportRun(FinancialBase):
    __tablename__ = "accounting_audit_export_runs"
    __table_args__ = (
        Index("ix_audit_export_runs_tenant", "tenant_id"),
        Index("ix_audit_export_runs_entity", "entity_id"),
        Index("ix_audit_export_runs_requested_by", "requested_by"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
    )
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)
    export_format: Mapped[str] = mapped_column(String(8), nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    r2_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

