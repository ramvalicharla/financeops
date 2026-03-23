from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class FDDEngagement(Base):
    __tablename__ = "fdd_engagements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','running','completed','failed','archived')",
            name="ck_fdd_engagements_status",
        ),
        Index("idx_fdd_engagements_tenant_status", "tenant_id", "status"),
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
    analysis_period_start: Mapped[date] = mapped_column(nullable=False)
    analysis_period_end: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'draft'"),
        default="draft",
    )
    credit_cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("2500"),
        default=2500,
    )
    credits_reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credits_deducted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sections_requested: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    sections_completed: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
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


class FDDSection(Base):
    __tablename__ = "fdd_sections"
    __table_args__ = (
        CheckConstraint(
            "section_name IN ('quality_of_earnings','working_capital','debt_liability','headcount','revenue_quality')",
            name="ck_fdd_sections_name",
        ),
        CheckConstraint(
            "status IN ('running','completed','failed')",
            name="ck_fdd_sections_status",
        ),
        Index("idx_fdd_sections_engagement_section", "engagement_id", "section_name"),
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
        ForeignKey("fdd_engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    ai_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)


class FDDFinding(Base):
    __tablename__ = "fdd_findings"
    __table_args__ = (
        CheckConstraint(
            "finding_type IN ('risk','adjustment','normalisation','information','positive')",
            name="ck_fdd_findings_type",
        ),
        CheckConstraint(
            "severity IN ('critical','high','medium','low','informational')",
            name="ck_fdd_findings_severity",
        ),
        Index("idx_fdd_findings_engagement_severity_type", "engagement_id", "severity", "finding_type"),
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
        ForeignKey("fdd_engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fdd_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    financial_impact: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    financial_impact_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'INR'"),
        default="INR",
    )
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["FDDEngagement", "FDDSection", "FDDFinding"]
