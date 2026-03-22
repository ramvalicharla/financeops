from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class WCSnapshot(Base):
    __tablename__ = "wc_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", "entity_id", name="uq_wc_snapshots_tenant_period_entity"),
        Index("idx_wc2_snapshots_tenant_period", "tenant_id", "period"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    ar_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ar_current: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ar_30: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ar_60: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ar_90: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    dso_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    ap_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ap_current: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ap_30: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ap_60: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ap_90: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    dpo_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    inventory_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    ccc_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    net_working_capital: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    current_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    quick_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ARLineItem(Base):
    __tablename__ = "ar_line_items"
    __table_args__ = (
        CheckConstraint(
            "aging_bucket IN ('current','days_30','days_60','days_90','over_90')",
            name="ck_ar_line_items_aging_bucket",
        ),
        Index("idx_wc2_ar_line_items_snapshot_bucket", "snapshot_id", "aging_bucket"),
        Index("idx_wc2_ar_line_items_snapshot_overdue_desc", "snapshot_id", text("days_overdue DESC")),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wc_snapshots.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"), default="INR")
    amount_base_currency: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    aging_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_probability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class APLineItem(Base):
    __tablename__ = "ap_line_items"
    __table_args__ = (
        CheckConstraint(
            "aging_bucket IN ('current','days_30','days_60','days_90','over_90')",
            name="ck_ap_line_items_aging_bucket",
        ),
        Index("idx_wc2_ap_line_items_snapshot_discount", "snapshot_id", "early_payment_discount_available"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wc_snapshots.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(300), nullable=False)
    vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"), default="INR")
    amount_base_currency: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    aging_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    early_payment_discount_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    early_payment_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["WCSnapshot", "ARLineItem", "APLineItem"]

