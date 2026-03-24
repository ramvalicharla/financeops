from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class CovenantDefinition(Base):
    __tablename__ = "covenant_definitions"
    __table_args__ = (
        Index("idx_covenant_definitions_tenant_active", "tenant_id", "is_active"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    facility_name: Mapped[str] = mapped_column(String(200), nullable=False)
    lender_name: Mapped[str] = mapped_column(String(200), nullable=False)
    covenant_type: Mapped[str] = mapped_column(String(50), nullable=False)
    covenant_label: Mapped[str] = mapped_column(String(200), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    threshold_direction: Mapped[str] = mapped_column(String(10), nullable=False)
    measurement_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    notification_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("90"), default=Decimal("90.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CovenantBreachEvent(Base):
    __tablename__ = "covenant_breach_events"
    __table_args__ = (
        Index("idx_covenant_breach_events_covenant_period", "covenant_id", "period"),
        Index("idx_covenant_breach_events_tenant_type_created", "tenant_id", "breach_type", "computed_at"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    covenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    actual_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(20), nullable=False)
    variance_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["CovenantDefinition", "CovenantBreachEvent"]
