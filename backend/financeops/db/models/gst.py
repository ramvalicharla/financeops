from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base, FinancialBase


class GstReturn(FinancialBase):
    """
    GST return data record — INSERT ONLY.
    Each return filing (GSTR-1, GSTR-3B, GSTR-2A, GSTR-2B) is one row.
    """
    __tablename__ = "gst_returns"
    __table_args__ = (
        Index("idx_gst_returns_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_gst_returns_entity_id", "tenant_id", "entity_id"),
        Index("idx_gst_returns_entity", "tenant_id", "entity_name"),
        Index("idx_gst_returns_type", "tenant_id", "return_type"),
        Index("idx_gst_returns_tenant_created", "tenant_id", "created_at"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id"),
        nullable=False,
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
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
    gstin: Mapped[str] = mapped_column(String(20), nullable=False)  # GST Identification Number
    # return_type: GSTR1 / GSTR3B / GSTR2A / GSTR2B
    return_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Tax amounts
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    cess_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    total_tax: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # status: draft / filed / reconciled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    filed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class GstReconItem(FinancialBase):
    """
    GST reconciliation break between two return types — INSERT ONLY.
    Compares GSTR-1 vs GSTR-3B (and similar) for the same period.
    """
    __tablename__ = "gst_recon_items"
    __table_args__ = (
        Index("idx_gst_recon_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_gst_recon_entity_id", "tenant_id", "entity_id"),
        Index("idx_gst_recon_status", "tenant_id", "status"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id"),
        nullable=False,
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    return_type_a: Mapped[str] = mapped_column(String(20), nullable=False)
    return_type_b: Mapped[str] = mapped_column(String(20), nullable=False)
    return_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gst_returns.id"), nullable=False
    )
    return_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gst_returns.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. igst_amount
    value_a: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    value_b: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # status: open / explained / resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_item_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gst_return_line_items.id"),
        nullable=True,
    )
    line_item_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gst_return_line_items.id"),
        nullable=True,
    )
    supplier_gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gst_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rate_mismatch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    match_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    itc_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    itc_blocked_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reverse_itc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GstReturnLineItem(FinancialBase):
    """
    GST return line item — INSERT ONLY.
    Stores invoice-level evidence imported from GSTR-1/GSTR-2B payloads.
    """

    __tablename__ = "gst_return_line_items"
    __table_args__ = (
        Index("idx_gst_return_line_items_return", "tenant_id", "gst_return_id"),
        Index("idx_gst_return_line_items_invoice", "tenant_id", "supplier_gstin", "invoice_number"),
    )

    gst_return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gst_returns.id"),
        nullable=False,
    )
    return_type: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_gstin: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(128), nullable=False)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    cess_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    total_tax: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    gst_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expense_category: Mapped[str | None] = mapped_column(String(64), nullable=True)


class GstRateMaster(Base):
    __tablename__ = "gst_rate_master"
    __table_args__ = (
        UniqueConstraint("rate", name="uq_gst_rate_master_rate"),
        Index("idx_gst_rate_master_rate", "rate"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(String(128), nullable=True)
