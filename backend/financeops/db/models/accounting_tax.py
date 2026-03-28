from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class GSTType:
    CGST = "CGST"
    SGST = "SGST"
    IGST = "IGST"
    EXEMPT = "EXEMPT"
    NIL = "NIL"
    ALL = frozenset({CGST, SGST, IGST, EXEMPT, NIL})


class TDSSection:
    S194C = "194C"
    S194J = "194J"
    S194I = "194I"
    ALL = frozenset({S194C, S194J, S194I})


class TaxOutcome:
    SUCCESS = "SUCCESS"
    MANUAL_FLAG = "MANUAL_FLAG"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    ALL = frozenset({SUCCESS, MANUAL_FLAG, SKIPPED, ERROR})


class AccountingGSTRule(FinancialBase):
    __tablename__ = "accounting_gst_rules"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gst_type: Mapped[str] = mapped_column(String(8), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountingTDSRule(FinancialBase):
    __tablename__ = "accounting_tds_rules"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_vendors.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    tds_section: Mapped[str] = mapped_column(String(16), nullable=False)
    section_description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tds_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    threshold_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    surcharge_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    cess_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountingTaxDeterminationLog(FinancialBase):
    __tablename__ = "accounting_tax_determination_logs"

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    jv_version: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_type: Mapped[str] = mapped_column(String(16), nullable=False)
    gst_sub_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tds_section: Mapped[str | None] = mapped_column(String(16), nullable=True)
    supplier_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    buyer_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    igst_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    tds_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gst_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_gst_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    tds_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_tds_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    determined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
