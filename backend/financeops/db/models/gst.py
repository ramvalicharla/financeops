from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


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
