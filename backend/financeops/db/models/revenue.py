from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class RevenueRun(FinancialBase):
    __tablename__ = "revenue_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_revenue_runs_tenant_signature"),
        Index("idx_revenue_runs_tenant_created", "tenant_id", "created_at"),
    )

    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RevenueRunEvent(FinancialBase):
    __tablename__ = "revenue_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_revenue_run_events_seq"),
        UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_revenue_run_events_idempotent",
        ),
        Index("idx_revenue_run_events_tenant_run", "tenant_id", "run_id", "event_seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RevenueContract(FinancialBase):
    __tablename__ = "revenue_contracts"
    __table_args__ = (
        Index("idx_revenue_contracts_tenant_number", "tenant_id", "contract_number", "created_at"),
        Index("idx_revenue_contracts_tenant_source", "tenant_id", "source_contract_reference"),
    )

    contract_number: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_contract_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="SET NULL"),
        nullable=True,
    )


class RevenuePerformanceObligation(FinancialBase):
    __tablename__ = "revenue_performance_obligations"
    __table_args__ = (
        Index("idx_revenue_obligations_contract", "tenant_id", "contract_id"),
        Index("idx_revenue_obligations_method", "tenant_id", "recognition_method"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obligation_code: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    standalone_selling_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    allocation_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    recognition_method: Mapped[str] = mapped_column(String(64), nullable=False)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_performance_obligations.id", ondelete="SET NULL"),
        nullable=True,
    )


class RevenueContractLineItem(FinancialBase):
    __tablename__ = "revenue_contract_line_items"
    __table_args__ = (
        Index("idx_revenue_line_items_contract", "tenant_id", "contract_id"),
        Index("idx_revenue_line_items_obligation", "tenant_id", "obligation_id"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_performance_obligations.id", ondelete="SET NULL"),
        nullable=True,
    )
    line_code: Mapped[str] = mapped_column(String(128), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    line_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    milestone_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usage_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contract_line_items.id", ondelete="SET NULL"),
        nullable=True,
    )


class RevenueSchedule(FinancialBase):
    __tablename__ = "revenue_schedules"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "contract_id",
            "recognition_date",
            "schedule_version_token",
            name="uq_revenue_schedules_natural",
        ),
        UniqueConstraint(
            "run_id",
            "contract_id",
            "period_seq",
            "schedule_version_token",
            name="uq_revenue_schedules_contract_period_version",
        ),
        Index("idx_revenue_schedules_run", "tenant_id", "run_id", "recognition_date"),
        Index("idx_revenue_schedules_contract", "tenant_id", "contract_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_performance_obligations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contract_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contract_line_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    recognition_date: Mapped[date] = mapped_column(Date, nullable=False)
    recognition_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    recognition_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    recognition_method: Mapped[str] = mapped_column(String(64), nullable=False)
    base_amount_contract_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    recognized_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cumulative_recognized_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RevenueJournalEntry(FinancialBase):
    __tablename__ = "revenue_journal_entries"
    __table_args__ = (
        Index("idx_revenue_journal_run", "tenant_id", "run_id", "entry_date"),
        Index("idx_revenue_journal_contract", "tenant_id", "contract_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_performance_obligations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_schedules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    journal_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RevenueAdjustment(FinancialBase):
    __tablename__ = "revenue_adjustments"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "contract_id",
            "effective_date",
            "adjustment_type",
            "idempotency_key",
            name="uq_revenue_adjustments_idempotent",
        ),
        Index("idx_revenue_adjustments_run", "tenant_id", "run_id", "effective_date"),
        Index("idx_revenue_adjustments_contract", "tenant_id", "contract_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment_reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prior_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    new_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_schedule_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_schedule_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    catch_up_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_contract_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_adjustments.id", ondelete="SET NULL"),
        nullable=True,
    )
