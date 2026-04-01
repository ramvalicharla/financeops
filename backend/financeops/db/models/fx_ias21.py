from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base, FinancialBase


class FxRateType:
    SPOT = "SPOT"
    AVERAGE = "AVERAGE"
    CLOSING = "CLOSING"
    ALL = frozenset({SPOT, AVERAGE, CLOSING})


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        Index(
            "ix_fx_rates_pair_effective_type",
            "from_currency",
            "to_currency",
            "effective_date",
            "rate_type",
        ),
        Index(
            "ix_fx_rates_tenant_pair_effective_type",
            "tenant_id",
            "from_currency",
            "to_currency",
            "effective_date",
            "rate_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AccountingFxRevaluationRun(FinancialBase):
    __tablename__ = "accounting_fx_revaluation_runs"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    closing_rate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    adjustment_jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="SET NULL"),
        nullable=True,
    )


class AccountingFxRevaluationLine(FinancialBase):
    __tablename__ = "accounting_fx_revaluation_lines"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_fx_revaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(300), nullable=False)
    transaction_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    functional_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    foreign_balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    historical_base_balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    closing_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    revalued_base_balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fx_difference: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)


class ConsolidationTranslationRun(FinancialBase):
    __tablename__ = "consolidation_translation_runs"

    org_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    presentation_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class ConsolidationTranslationEntityResult(FinancialBase):
    __tablename__ = "consolidation_translation_entity_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consolidation_translation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    functional_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    presentation_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    closing_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    average_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    translated_assets: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    translated_liabilities: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    translated_equity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    translated_net_profit: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cta_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

