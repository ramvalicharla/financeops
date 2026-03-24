from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"
    __table_args__ = (
        CheckConstraint(
            "partner_tier IN ('referral','reseller','technology')",
            name="ck_partner_profiles_tier",
        ),
        UniqueConstraint("tenant_id", name="uq_partner_profiles_tenant"),
        UniqueConstraint("partner_code", name="uq_partner_profiles_code"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    partner_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'referral'"),
        default="referral",
    )
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(300), nullable=False)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    partner_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    commission_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    total_referrals: Mapped[int] = mapped_column(
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    total_commissions_earned: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    stripe_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class ReferralTracking(Base):
    __tablename__ = "referral_tracking"
    __table_args__ = (
        CheckConstraint(
            "status IN ('clicked','signed_up','converted','churned','expired')",
            name="ck_referral_tracking_status",
        ),
        Index("idx_referral_tracking_referral_code", "referral_code"),
        Index("idx_referral_tracking_partner_status", "partner_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partner_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    referred_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    referral_code: Mapped[str] = mapped_column(String(20), nullable=False)
    referral_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'clicked'"),
        default="clicked",
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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


class PartnerCommission(Base):
    __tablename__ = "partner_commissions"
    __table_args__ = (
        CheckConstraint(
            "commission_type IN ('first_payment','recurring','technology_rev_share')",
            name="ck_partner_commissions_type",
        ),
        CheckConstraint(
            "status IN ('pending','approved','paid','cancelled')",
            name="ck_partner_commissions_status",
        ),
        Index("idx_partner_commissions_partner_status_created", "partner_id", "status", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    referral_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referral_tracking.id", ondelete="RESTRICT"),
        nullable=False,
    )
    referred_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    commission_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    period: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["PartnerCommission", "PartnerProfile", "ReferralTracking"]

