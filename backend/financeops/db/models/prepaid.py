from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class PrepaidRun(FinancialBase):
    __tablename__ = "prepaid_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_prepaid_runs_tenant_signature"),
        Index("idx_prepaid_runs_tenant_created", "tenant_id", "created_at"),
    )

    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PrepaidRunEvent(FinancialBase):
    __tablename__ = "prepaid_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_prepaid_run_events_seq"),
        UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_prepaid_run_events_idempotent",
        ),
        Index("idx_prepaid_run_events_tenant_run", "tenant_id", "run_id", "event_seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Prepaid(FinancialBase):
    __tablename__ = "prepaids"
    __table_args__ = (
        Index("idx_prepaids_tenant_code", "tenant_id", "prepaid_code", "created_at"),
        Index("idx_prepaids_tenant_source", "tenant_id", "source_expense_reference"),
    )

    prepaid_code: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    prepaid_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    term_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_amount_contract_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    period_frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern_json_normalized: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rate_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_expense_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaids.id", ondelete="SET NULL"),
        nullable=True,
    )


class PrepaidAmortizationSchedule(FinancialBase):
    __tablename__ = "prepaid_amortization_schedule"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "prepaid_id",
            "amortization_date",
            "schedule_version_token",
            name="uq_prepaid_schedule_date_version",
        ),
        UniqueConstraint(
            "run_id",
            "prepaid_id",
            "period_seq",
            "schedule_version_token",
            name="uq_prepaid_schedule_period_version",
        ),
        Index("idx_prepaid_schedule_tenant_run", "tenant_id", "run_id", "amortization_date"),
        Index("idx_prepaid_schedule_tenant_prepaid", "tenant_id", "prepaid_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prepaid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaids.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    amortization_date: Mapped[date] = mapped_column(Date, nullable=False)
    recognition_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    recognition_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    base_amount_contract_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amortized_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cumulative_amortized_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    fx_rate_source: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_expense_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PrepaidJournalEntry(FinancialBase):
    __tablename__ = "prepaid_journal_entries"
    __table_args__ = (
        Index("idx_prepaid_journal_tenant_run", "tenant_id", "run_id", "entry_date"),
        Index("idx_prepaid_journal_tenant_prepaid", "tenant_id", "prepaid_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prepaid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaids.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_amortization_schedule.id", ondelete="RESTRICT"),
        nullable=False,
    )
    journal_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_expense_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PrepaidAdjustment(FinancialBase):
    __tablename__ = "prepaid_adjustments"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "prepaid_id",
            "effective_date",
            "adjustment_type",
            "idempotency_key",
            name="uq_prepaid_adjustments_idempotent",
        ),
        Index("idx_prepaid_adjustments_tenant_run", "tenant_id", "run_id", "effective_date"),
        Index("idx_prepaid_adjustments_tenant_prepaid", "tenant_id", "prepaid_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prepaid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaids.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment_reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prior_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    new_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    catch_up_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_expense_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_adjustments.id", ondelete="SET NULL"),
        nullable=True,
    )
