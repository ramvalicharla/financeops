from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class MultiGAAPConfig(Base):
    __tablename__ = "multi_gaap_configs"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    primary_gaap: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'INDAS'"), default="INDAS")
    secondary_gaaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    revenue_recognition_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    lease_classification_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    financial_instruments_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class MultiGAAPRun(Base):
    __tablename__ = "multi_gaap_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", "gaap_framework", name="uq_multi_gaap_runs_tenant_period_framework"),
        Index("idx_multi_gaap_runs_tenant_period_framework", "tenant_id", "period", "gaap_framework"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    gaap_framework: Mapped[str] = mapped_column(String(20), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ebitda: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ebit: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    profit_before_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    profit_after_tax: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    adjustments: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["MultiGAAPConfig", "MultiGAAPRun"]
