from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class GlEntry(FinancialBase):
    """
    General Ledger entry — INSERT ONLY.
    Each GL import creates rows here.  Summation by account gives TB equivalent.
    """
    __tablename__ = "gl_entries"
    __table_args__ = (
        Index("idx_gl_entries_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_gl_entries_account", "tenant_id", "account_code"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ERP reference
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")  # ISO 4217
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class TrialBalanceRow(FinancialBase):
    """
    Trial Balance row — INSERT ONLY.
    Closing balance per account per period per entity.
    """
    __tablename__ = "trial_balance_rows"
    __table_args__ = (
        Index("idx_tb_rows_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_tb_rows_account", "tenant_id", "account_code"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    period_debit: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    period_credit: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ReconItem(FinancialBase):
    """
    GL vs TB reconciliation break — INSERT ONLY.
    Each recon run creates new rows.  Status changes create new rows.
    """
    __tablename__ = "recon_items"
    __table_args__ = (
        Index("idx_recon_items_tenant_period", "tenant_id", "period_year", "period_month"),
        Index("idx_recon_items_status", "tenant_id", "status"),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Entity scope for multi-entity tenants",
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gl_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tb_closing_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    # status: open / in_progress / resolved / escalated
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # recon_type: gl_tb / intercompany
    recon_type: Mapped[str] = mapped_column(String(50), nullable=False, default="gl_tb")
    run_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
