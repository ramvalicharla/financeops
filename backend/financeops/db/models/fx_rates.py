from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class FxRateFetchRun(FinancialBase):
    """
    Live fetch execution metadata for a currency pair and date.
    Immutable append-only run log for provider health and selected-rate traceability.
    """

    __tablename__ = "fx_rate_fetch_runs"
    __table_args__ = (
        Index(
            "idx_fx_fetch_runs_tenant_pair_date",
            "tenant_id",
            "base_currency",
            "quote_currency",
            "rate_date",
        ),
        Index("idx_fx_fetch_runs_tenant_created", "tenant_id", "created_at"),
    )

    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success / degraded / failed
    provider_count: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    selected_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selection_method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_errors: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)


class FxRateQuote(FinancialBase):
    """
    Normalized raw provider observation for one pair/date.
    Canonical convention: 1 base_currency = X quote_currency.
    """

    __tablename__ = "fx_rate_quotes"
    __table_args__ = (
        Index(
            "idx_fx_quotes_tenant_pair_date_provider",
            "tenant_id",
            "base_currency",
            "quote_currency",
            "rate_date",
            "provider_name",
        ),
        Index("idx_fx_quotes_fetch_run", "tenant_id", "fetch_run_id"),
    )

    fetch_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_rate_fetch_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class FxManualMonthlyRate(FinancialBase):
    """
    Manual monthly rate profile entries.
    Append-only; supersession and month-end locking are represented as new rows only.
    """

    __tablename__ = "fx_manual_monthly_rates"
    __table_args__ = (
        Index(
            "idx_fx_manual_tenant_period_pair",
            "tenant_id",
            "period_year",
            "period_month",
            "base_currency",
            "quote_currency",
        ),
        Index("idx_fx_manual_tenant_created", "tenant_id", "created_at"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    entered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fx_manual_monthly_rates.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    is_month_end_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FxVarianceResult(FinancialBase):
    """
    Expected-vs-actual FX variance output for IC explanation consumers.
    """

    __tablename__ = "fx_variance_results"
    __table_args__ = (
        Index(
            "idx_fx_variance_tenant_period_pair",
            "tenant_id",
            "period_year",
            "period_month",
            "base_currency",
            "quote_currency",
        ),
        Index("idx_fx_variance_tenant_created", "tenant_id", "created_at"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    expected_difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    actual_difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fx_variance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    computed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
