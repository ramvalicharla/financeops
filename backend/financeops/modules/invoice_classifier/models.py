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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class InvoiceClassification(Base):
    __tablename__ = "invoice_classifications"
    __table_args__ = (
        Index("idx_invoice_classifications_tenant_id", "tenant_id"),
        Index("idx_invoice_classifications_entity_id", "entity_id"),
        Index("idx_invoice_classifications_requires_human_review", "requires_human_review"),
        Index("idx_invoice_classifications_routing_action", "routing_action"),
        Index("idx_invoice_classifications_classification", "classification"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    classification_method: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_matched: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    human_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    human_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    human_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    routing_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    routed_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClassificationRule(Base):
    __tablename__ = "classification_rules"
    __table_args__ = (
        Index("idx_classification_rules_tenant_id", "tenant_id"),
        Index("idx_classification_rules_priority", "priority"),
        Index("idx_classification_rules_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pattern_type: Mapped[str] = mapped_column(String(30), nullable=False)
    pattern_value: Mapped[str] = mapped_column(String(500), nullable=False)
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"), default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["InvoiceClassification", "ClassificationRule"]
