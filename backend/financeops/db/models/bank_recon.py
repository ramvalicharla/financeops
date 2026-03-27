from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class BankStatement(FinancialBase):
    """
    Bank statement upload header — INSERT ONLY.
    One row per statement file uploaded.
    """
    __tablename__ = "bank_statements"
    __table_args__ = (
        Index("idx_bank_stmts_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_bank_stmts_entity_id", "tenant_id", "entity_id"),
        Index("idx_bank_stmts_entity", "tenant_id", "entity_name"),
    )

    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number_masked: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. ****1234
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
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
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # status: pending / processed / error
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BankTransaction(FinancialBase):
    """
    Individual bank statement line — INSERT ONLY.
    """
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("idx_bank_txns_statement", "tenant_id", "statement_id"),
        Index("idx_bank_txns_entity_id", "tenant_id", "entity_id"),
        Index("idx_bank_txns_match", "tenant_id", "match_status"),
    )

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_statements.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id"),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # match_status: unmatched / matched / excluded
    match_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unmatched")


class BankReconItem(FinancialBase):
    """
    Bank reconciliation item — INSERT ONLY.
    Represents a break or match between bank and GL.
    """
    __tablename__ = "bank_recon_items"
    __table_args__ = (
        Index("idx_bank_recon_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_bank_recon_entity_id", "tenant_id", "entity_id"),
        Index("idx_bank_recon_status", "tenant_id", "status"),
    )

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_statements.id"), nullable=False
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id"),
        nullable=False,
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # item_type: bank_only / gl_only / reconciled / timing_difference
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bank_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    gl_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    # status: open / resolved
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
