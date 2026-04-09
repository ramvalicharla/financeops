from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class WorkingCapitalSnapshot(FinancialBase):
    """
    Working capital point-in-time snapshot — INSERT ONLY.
    Calculated from uploaded GL/TB data and stored for dashboard rendering.
    """
    __tablename__ = "working_capital_snapshots"
    __table_args__ = (
        Index("idx_wc_snapshots_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_wc_snapshots_entity", "tenant_id", "entity_name"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Current assets
    cash_and_equivalents: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    accounts_receivable: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    inventory: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    prepaid_expenses: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    other_current_assets: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    total_current_assets: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)

    # Current liabilities
    accounts_payable: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    accrued_liabilities: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    short_term_debt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    other_current_liabilities: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    total_current_liabilities: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)

    # Ratios (computed at write time, stored for fast reads)
    working_capital: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    current_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    quick_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cash_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
