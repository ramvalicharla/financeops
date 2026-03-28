from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class FarRun(FinancialBase):
    __tablename__ = "far_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_signature", name="uq_far_runs_tenant_signature"),
        Index("idx_far_runs_tenant_created", "tenant_id", "created_at"),
    )

    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FarRunEvent(FinancialBase):
    __tablename__ = "far_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="uq_far_run_events_seq"),
        UniqueConstraint("run_id", "event_type", "idempotency_key", name="uq_far_run_events_idempotent"),
        Index("idx_far_run_events_tenant_run", "tenant_id", "run_id", "event_seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("far_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Asset(FinancialBase):
    __tablename__ = "assets"
    __table_args__ = (
        Index("idx_assets_tenant_code", "tenant_id", "asset_code", "created_at"),
        Index("idx_assets_tenant_source", "tenant_id", "source_acquisition_reference"),
    )

    asset_code: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reporting_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    capitalization_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    in_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    capitalized_amount_asset_currency: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    depreciation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    useful_life_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reducing_balance_rate_annual: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    residual_value_reporting_currency: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    rate_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_acquisition_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )


class AssetDepreciationSchedule(FinancialBase):
    __tablename__ = "asset_depreciation_schedule"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "asset_id",
            "depreciation_date",
            "schedule_version_token",
            name="uq_asset_schedule_date_version",
        ),
        UniqueConstraint(
            "run_id",
            "asset_id",
            "period_seq",
            "schedule_version_token",
            name="uq_asset_schedule_period_version",
        ),
        Index("idx_asset_schedule_tenant_run", "tenant_id", "run_id", "depreciation_date"),
        Index("idx_asset_schedule_tenant_asset", "tenant_id", "asset_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("far_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_date: Mapped[date] = mapped_column(Date, nullable=False)
    depreciation_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_carrying_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    depreciation_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cumulative_depreciation_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    closing_carrying_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    fx_rate_source: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_acquisition_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AssetImpairment(FinancialBase):
    __tablename__ = "asset_impairments"
    __table_args__ = (
        UniqueConstraint("run_id", "asset_id", "impairment_date", "idempotency_key", name="uq_asset_impairments_idempotent"),
        Index("idx_asset_impairments_tenant_run", "tenant_id", "run_id", "impairment_date"),
        Index("idx_asset_impairments_tenant_asset", "tenant_id", "asset_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("far_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    impairment_date: Mapped[date] = mapped_column(Date, nullable=False)
    impairment_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prior_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    new_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    fx_rate_source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_acquisition_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_impairments.id", ondelete="SET NULL"),
        nullable=True,
    )


class AssetDisposal(FinancialBase):
    __tablename__ = "asset_disposals"
    __table_args__ = (
        UniqueConstraint("run_id", "asset_id", "disposal_date", "idempotency_key", name="uq_asset_disposals_idempotent"),
        Index("idx_asset_disposals_tenant_run", "tenant_id", "run_id", "disposal_date"),
        Index("idx_asset_disposals_tenant_asset", "tenant_id", "asset_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("far_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    disposal_date: Mapped[date] = mapped_column(Date, nullable=False)
    proceeds_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    disposal_cost_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    carrying_amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    gain_loss_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    prior_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    new_schedule_version_token: Mapped[str] = mapped_column(String(64), nullable=False)
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    fx_rate_source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_acquisition_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_disposals.id", ondelete="SET NULL"),
        nullable=True,
    )


class AssetJournalEntry(FinancialBase):
    __tablename__ = "asset_journal_entries"
    __table_args__ = (
        UniqueConstraint("run_id", "journal_reference", "line_seq", name="uq_asset_journal_run_ref_line"),
        CheckConstraint(
            "(CASE WHEN depreciation_schedule_id IS NOT NULL THEN 1 ELSE 0 END + "
            " CASE WHEN impairment_id IS NOT NULL THEN 1 ELSE 0 END +"
            " CASE WHEN disposal_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_asset_journal_exactly_one_source",
        ),
        Index("idx_asset_journal_tenant_run", "tenant_id", "run_id", "entry_date"),
        Index("idx_asset_journal_tenant_asset", "tenant_id", "asset_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("far_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    depreciation_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_depreciation_schedule.id", ondelete="SET NULL"),
        nullable=True,
    )
    impairment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_impairments.id", ondelete="SET NULL"),
        nullable=True,
    )
    disposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_disposals.id", ondelete="SET NULL"),
        nullable=True,
    )
    journal_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    line_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_reporting_currency: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_acquisition_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
