from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        CheckConstraint(
            "forecast_type IN ('rolling_12','annual','quarterly')",
            name="ck_forecast_runs_type",
        ),
        CheckConstraint(
            "status IN ('draft','published','superseded')",
            name="ck_forecast_runs_status",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_name: Mapped[str] = mapped_column(String(200), nullable=False)
    forecast_type: Mapped[str] = mapped_column(String(20), nullable=False)
    base_period: Mapped[str] = mapped_column(String(7), nullable=False)
    horizon_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        default="draft",
    )
    is_published: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ForecastAssumption(Base):
    __tablename__ = "forecast_assumptions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('growth','margins','headcount','fx','capex','other')",
            name="ck_forecast_assumptions_category",
        ),
        UniqueConstraint(
            "forecast_run_id",
            "assumption_key",
            name="uq_forecast_assumptions_run_key",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assumption_key: Mapped[str] = mapped_column(String(100), nullable=False)
    assumption_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    assumption_label: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ForecastLineItem(Base):
    __tablename__ = "forecast_line_items"
    __table_args__ = (
        Index("idx_forecast_line_items_run_period_line", "forecast_run_id", "period", "mis_line_item"),
        Index("idx_forecast_line_items_tenant_period", "tenant_id", "period"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    is_actual: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    mis_line_item: Mapped[str] = mapped_column(String(300), nullable=False)
    mis_category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["ForecastRun", "ForecastAssumption", "ForecastLineItem"]

