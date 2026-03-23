from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class PPAEngagement(Base):
    __tablename__ = "ppa_engagements"
    __table_args__ = (
        CheckConstraint("accounting_standard IN ('IFRS3','ASC805','INDAS103')", name="ck_ppa_engagements_standard"),
        CheckConstraint("status IN ('draft','running','completed','failed')", name="ck_ppa_engagements_status"),
        Index("idx_ppa_engagements_tenant_status", "tenant_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    engagement_name: Mapped[str] = mapped_column(String(300), nullable=False)
    target_company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    purchase_price_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'INR'"),
        default="INR",
    )
    accounting_standard: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        default="draft",
    )
    credit_cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("2000"),
        default=2000,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class PPAAllocation(Base):
    __tablename__ = "ppa_allocations"
    __table_args__ = (
        Index("idx_ppa_allocations_engagement", "engagement_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ppa_engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    allocation_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    net_identifiable_assets: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_intangibles_identified: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    goodwill: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    deferred_tax_liability: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    purchase_price_reconciliation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class PPAIntangible(Base):
    __tablename__ = "ppa_intangibles"
    __table_args__ = (
        CheckConstraint(
            "intangible_category IN ('customer_relationships','technology','brand','contracts','non_compete','in_process_rd','other')",
            name="ck_ppa_intangibles_category",
        ),
        CheckConstraint(
            "amortisation_method IN ('straight_line','accelerated','unit_of_production')",
            name="ck_ppa_intangibles_amortisation",
        ),
        CheckConstraint(
            "valuation_method IN ('relief_from_royalty','excess_earnings','cost_approach','market_approach','with_without')",
            name="ck_ppa_intangibles_valuation_method",
        ),
        Index("idx_ppa_intangibles_engagement_category", "engagement_id", "intangible_category"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ppa_engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ppa_allocations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intangible_name: Mapped[str] = mapped_column(String(200), nullable=False)
    intangible_category: Mapped[str] = mapped_column(String(50), nullable=False)
    fair_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    useful_life_years: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    amortisation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_amortisation: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    tax_basis: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    deferred_tax_liability: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    valuation_method: Mapped[str] = mapped_column(String(50), nullable=False)
    valuation_assumptions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["PPAEngagement", "PPAAllocation", "PPAIntangible"]
