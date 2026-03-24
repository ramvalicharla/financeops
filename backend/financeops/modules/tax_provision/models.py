from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class TaxProvisionRun(Base):
    __tablename__ = "tax_provision_runs"
    __table_args__ = (
        Index("idx_tax_provision_runs_tenant_period", "tenant_id", "period"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    applicable_tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    accounting_profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    permanent_differences: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    timing_differences: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    current_tax_expense: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)

    deferred_tax_asset: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    deferred_tax_liability: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    net_deferred_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)

    total_tax_expense: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    effective_tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class TaxPosition(Base):
    __tablename__ = "tax_positions"
    __table_args__ = (
        Index("idx_tax_positions_tenant_type", "tenant_id", "position_type"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position_name: Mapped[str] = mapped_column(String(200), nullable=False)
    position_type: Mapped[str] = mapped_column(String(30), nullable=False)
    carrying_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    tax_base: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    temporary_difference: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    deferred_tax_impact: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    is_asset: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["TaxProvisionRun", "TaxPosition"]
