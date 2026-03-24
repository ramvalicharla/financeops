from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class MarketplaceContributor(Base):
    __tablename__ = "marketplace_contributors"
    __table_args__ = (
        CheckConstraint(
            "contributor_tier IN ('community','verified_partner','platform_official')",
            name="ck_marketplace_contributors_tier",
        ),
        CheckConstraint(
            "revenue_share_pct >= 0 AND revenue_share_pct <= 1",
            name="ck_marketplace_contributors_revenue_share_pct",
        ),
        UniqueConstraint("tenant_id", name="uq_marketplace_contributors_tenant_id"),
        {"extend_existing": True},
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
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    contributor_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'community'"),
        default="community",
    )
    revenue_share_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default=text("0.6000"),
        default=Decimal("0.6000"),
    )
    stripe_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_earnings: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    total_templates: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    total_downloads: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    rating_average: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
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


class MarketplaceTemplate(Base):
    __tablename__ = "marketplace_templates"
    __table_args__ = (
        CheckConstraint(
            "template_type IN ("
            "'mis_template','report_template','board_pack','classification_mapping',"
            "'consolidation_template','paysheet_template','industry_pack','fdd_template',"
            "'budget_template','forecast_template'"
            ")",
            name="ck_marketplace_templates_template_type",
        ),
        CheckConstraint(
            "industry IN ("
            "'saas','manufacturing','retail','professional_services','healthcare',"
            "'it_services','general','fsi','ecommerce'"
            ") OR industry IS NULL",
            name="ck_marketplace_templates_industry",
        ),
        CheckConstraint(
            "status IN ('draft','pending_review','published','rejected','archived')",
            name="ck_marketplace_templates_status",
        ),
        Index(
            "idx_marketplace_templates_status_type_industry",
            "status",
            "template_type",
            "industry",
        ),
        Index("idx_marketplace_templates_contributor_id", "contributor_id"),
        Index("idx_marketplace_templates_featured_status", "is_featured", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_contributors.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    is_free: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    template_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    preview_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    rating_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    rating_sum: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    rating_average: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default=text("0"),
        default=Decimal("0"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        default="draft",
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
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


class MarketplacePurchase(Base):
    __tablename__ = "marketplace_purchases"
    __table_args__ = (
        Index("idx_marketplace_purchases_buyer_purchased_at", "buyer_tenant_id", "purchased_at"),
        Index("idx_marketplace_purchases_contributor_purchased_at", "contributor_id", "purchased_at"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    buyer_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_contributors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price_credits_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_share_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    contributor_share_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    contributor_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'completed'"),
        default="completed",
    )
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class MarketplacePayout(Base):
    __tablename__ = "marketplace_payouts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="ck_marketplace_payouts_status",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_contributors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_credits_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    total_usd_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        default="pending",
    )
    stripe_transfer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class MarketplaceRating(Base):
    __tablename__ = "marketplace_ratings"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_marketplace_ratings_rating"),
        UniqueConstraint(
            "template_id",
            "buyer_tenant_id",
            name="uq_marketplace_ratings_template_buyer",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    buyer_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "MarketplaceContributor",
    "MarketplaceTemplate",
    "MarketplacePurchase",
    "MarketplacePayout",
    "MarketplaceRating",
]

