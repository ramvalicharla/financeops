from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class LeaseRun(FinancialBase):
    __tablename__ = "lease_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_lease_runs_tenant_signature"),
        Index("idx_lease_runs_tenant_created", "tenant_id", "created_at"),
    )

    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LeaseRunEvent(FinancialBase):
    __tablename__ = "lease_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_lease_run_events_seq"),
        UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_lease_run_events_idempotent",
        ),
        Index("idx_lease_run_events_tenant_run", "tenant_id", "run_id", "event_seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Lease(FinancialBase):
    __tablename__ = "leases"
    __table_args__ = (
        Index("idx_leases_tenant_number", "tenant_id", "lease_number", "created_at"),
        Index("idx_leases_tenant_source", "tenant_id", "source_lease_reference"),
    )

    lease_number: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counterparty_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lease_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    commencement_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_discount_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    discount_rate_source: Mapped[str] = mapped_column(String(64), nullable=False)
    discount_rate_reference_date: Mapped[date] = mapped_column(Date, nullable=False)
    discount_rate_policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    initial_measurement_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True,
    )


class LeasePayment(FinancialBase):
    __tablename__ = "lease_payments"
    __table_args__ = (
        Index("idx_lease_payments_lease", "tenant_id", "lease_id", "payment_sequence"),
        UniqueConstraint("tenant_id", "lease_id", "payment_sequence", name="uq_lease_payments_sequence"),
    )

    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_amount_lease_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_payments.id", ondelete="SET NULL"),
        nullable=True,
    )


class LeaseLiabilitySchedule(FinancialBase):
    __tablename__ = "lease_liability_schedule"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "lease_id",
            "schedule_date",
            "schedule_version_token",
            name="uq_lease_liability_schedule_natural",
        ),
        UniqueConstraint(
            "run_id",
            "lease_id",
            "period_seq",
            "schedule_version_token",
            name="uq_lease_liability_schedule_period_version",
        ),
        Index("idx_lease_liability_schedule_run", "tenant_id", "run_id", "schedule_date"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    period_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_liability_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    interest_expense_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    payment_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    closing_liability_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LeaseRouSchedule(FinancialBase):
    __tablename__ = "lease_rou_schedule"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "lease_id",
            "schedule_date",
            "schedule_version_token",
            name="uq_lease_rou_schedule_natural",
        ),
        UniqueConstraint(
            "run_id",
            "lease_id",
            "period_seq",
            "schedule_version_token",
            name="uq_lease_rou_schedule_period_version",
        ),
        Index("idx_lease_rou_schedule_run", "tenant_id", "run_id", "schedule_date"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_rou_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amortization_expense_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    impairment_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    closing_rou_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LeaseModification(FinancialBase):
    __tablename__ = "lease_modifications"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "lease_id",
            "effective_date",
            "modification_type",
            "idempotency_key",
            name="uq_lease_modifications_idempotent",
        ),
        Index("idx_lease_modifications_run", "tenant_id", "run_id", "effective_date"),
        Index("idx_lease_modifications_lease", "tenant_id", "lease_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    modification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    modification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prior_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    new_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_schedule_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_schedule_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remeasurement_delta_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_modifications.id", ondelete="SET NULL"),
        nullable=True,
    )


class LeaseJournalEntry(FinancialBase):
    __tablename__ = "lease_journal_entries"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN liability_schedule_id IS NOT NULL THEN 1 ELSE 0 END + "
            " CASE WHEN rou_schedule_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_lease_journal_exactly_one_source",
        ),
        Index("idx_lease_journal_run", "tenant_id", "run_id", "entry_date"),
        Index("idx_lease_journal_lease", "tenant_id", "lease_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    liability_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_liability_schedule.id", ondelete="SET NULL"),
        nullable=True,
    )
    rou_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lease_rou_schedule.id", ondelete="SET NULL"),
        nullable=True,
    )
    journal_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_lease_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
