from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class TPConfig(Base):
    __tablename__ = "tp_configs"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    consolidated_revenue_threshold: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("50000000"), default=Decimal("50000000.00"))
    international_transactions_exist: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    specified_domestic_transactions_exist: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    applicable_methods: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ICTransaction(Base):
    __tablename__ = "ic_transactions"
    __table_args__ = (
        Index("idx_ic_transactions_tenant_fiscal_year", "tenant_id", "fiscal_year"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_party_name: Mapped[str] = mapped_column(String(300), nullable=False)
    related_party_country: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_amount_inr: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    pricing_method: Mapped[str] = mapped_column(String(10), nullable=False)
    arm_length_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    actual_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    adjustment_required: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    is_international: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class TransferPricingDoc(Base):
    __tablename__ = "transfer_pricing_docs"
    __table_args__ = (
        Index("idx_transfer_pricing_docs_tenant_year_type", "tenant_id", "fiscal_year", "document_type"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    ai_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"), default="draft")
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["TPConfig", "ICTransaction", "TransferPricingDoc"]
