from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class MAWorkspace(Base):
    __tablename__ = "ma_workspaces"
    __table_args__ = (
        CheckConstraint(
            "deal_type IN ('acquisition','merger','divestiture','minority_investment','joint_venture')",
            name="ck_ma_workspaces_deal_type",
        ),
        CheckConstraint(
            "deal_status IN ('active','paused','closed_won','closed_lost','on_hold')",
            name="ck_ma_workspaces_deal_status",
        ),
        Index("idx_ma_workspaces_tenant_status", "tenant_id", "deal_status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workspace_name: Mapped[str] = mapped_column(String(300), nullable=False)
    deal_codename: Mapped[str] = mapped_column(String(100), nullable=False)
    deal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    deal_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'active'"),
        default="active",
    )
    indicative_deal_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    deal_value_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'INR'"),
        default="INR",
    )
    credit_cost_monthly: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1000"),
        default=1000,
    )
    credit_charged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class MAWorkspaceMember(Base):
    __tablename__ = "ma_workspace_members"
    __table_args__ = (
        CheckConstraint(
            "member_role IN ('lead_advisor','analyst','observer','external_advisor')",
            name="ck_ma_workspace_members_role",
        ),
        UniqueConstraint("workspace_id", "user_id", name="uq_ma_workspace_members_workspace_user"),
        Index("idx_ma_workspace_members_workspace", "workspace_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ma_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    member_role: Mapped[str] = mapped_column(String(30), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MAValuation(Base):
    __tablename__ = "ma_valuations"
    __table_args__ = (
        CheckConstraint(
            "valuation_method IN ('dcf','comparable_companies','precedent_transactions','asset_based','lbo')",
            name="ck_ma_valuations_method",
        ),
        Index("idx_ma_valuations_workspace_computed", "workspace_id", "computed_at"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ma_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    valuation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    valuation_method: Mapped[str] = mapped_column(String(30), nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    enterprise_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    equity_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    net_debt_used: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    ev_ebitda_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    ev_revenue_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    valuation_range_low: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    valuation_range_high: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    computed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MADDItem(Base):
    __tablename__ = "ma_dd_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('financial','legal','tax','commercial','technical','hr','regulatory','environmental')",
            name="ck_ma_dd_items_category",
        ),
        CheckConstraint(
            "status IN ('open','in_progress','completed','flagged','waived')",
            name="ck_ma_dd_items_status",
        ),
        CheckConstraint(
            "priority IN ('critical','high','medium','low')",
            name="ck_ma_dd_items_priority",
        ),
        Index("idx_ma_dd_items_workspace_status", "workspace_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ma_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"), default="open")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'medium'"), default="medium")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("iam_users.id", ondelete="SET NULL"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class MADocument(Base):
    __tablename__ = "ma_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('nda','loi','spa','sha','disclosure_schedule','financial_model','dd_report','board_presentation','regulatory_filing','other')",
            name="ck_ma_documents_type",
        ),
        Index("idx_ma_documents_workspace_type", "workspace_id", "document_type"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ma_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_name: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_confidential: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["MAWorkspace", "MAWorkspaceMember", "MAValuation", "MADDItem", "MADocument"]
