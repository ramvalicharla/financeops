from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class CashFlowForecastRun(Base):
    __tablename__ = "cash_flow_forecast_runs"
    __table_args__ = (
        Index("idx_cash_flow_forecast_runs_tenant_base_date", "tenant_id", "base_date"),
        Index("idx_cash_flow_forecast_runs_entity_id", "entity_id"),
        Index("idx_cash_flow_forecast_runs_location_id", "location_id"),
        Index("idx_cash_flow_forecast_runs_cost_centre_id", "cost_centre_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    cost_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_cost_centres.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_date: Mapped[date] = mapped_column(Date, nullable=False)
    weeks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("13"), default=13)
    opening_cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"), default="INR")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"), default="draft")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CashFlowForecastAssumption(Base):
    __tablename__ = "cash_flow_forecast_assumptions"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "week_number", name="uq_cash_flow_forecast_assumptions_run_week"),
        Index("idx_cash_flow_forecast_assumptions_run_week", "forecast_run_id", "week_number"),
        Index("idx_cash_flow_forecast_assumptions_entity_id", "tenant_id", "entity_id"),
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
        ForeignKey("cash_flow_forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)

    customer_collections: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    other_inflows: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    supplier_payments: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    payroll: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    rent_and_utilities: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    loan_repayments: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    tax_payments: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    capex: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    other_outflows: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))

    total_inflows: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    total_outflows: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    net_cash_flow: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


@event.listens_for(CashFlowForecastRun, "before_insert")
def _default_entity_id_for_forecast_run(_, connection, target: CashFlowForecastRun) -> None:
    if target.entity_id is not None:
        return
    row = connection.execute(
        text(
            """
            SELECT id
            FROM cp_entities
            WHERE tenant_id = :tenant_id
              AND status = 'active'
            ORDER BY created_at ASC NULLS LAST, id ASC
            LIMIT 1
            """
        ),
        {"tenant_id": target.tenant_id},
    ).scalar_one_or_none()
    if row is None:
        row = connection.execute(
            text(
                """
                SELECT id
                FROM cp_entities
                WHERE status = 'active'
                ORDER BY created_at ASC NULLS LAST, id ASC
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
    if row is not None:
        target.entity_id = row


__all__ = [
    "CashFlowForecastRun",
    "CashFlowForecastAssumption",
]
