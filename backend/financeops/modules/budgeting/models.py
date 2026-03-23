from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class BudgetVersion(Base):
    __tablename__ = "budget_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','approved','superseded')",
            name="ck_budget_versions_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "fiscal_year",
            "version_number",
            name="uq_budget_versions_tenant_year_version",
        ),
        Index("idx_budget_versions_tenant_year", "tenant_id", "fiscal_year"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    version_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        default="draft",
    )
    is_board_approved: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    board_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    board_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"
    __table_args__ = (
        Index("idx_budget_line_items_version_line", "budget_version_id", "mis_line_item"),
        Index("idx_budget_line_items_tenant_version", "tenant_id", "budget_version_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    budget_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("budget_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    mis_line_item: Mapped[str] = mapped_column(String(300), nullable=False)
    mis_category: Mapped[str] = mapped_column(String(100), nullable=False)
    month_01: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_02: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_03: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_04: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_05: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_06: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_07: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_08: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_09: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_10: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_11: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    month_12: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    annual_total: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        Computed(
            "month_01 + month_02 + month_03 + month_04 + "
            "month_05 + month_06 + month_07 + month_08 + "
            "month_09 + month_10 + month_11 + month_12",
            persisted=True,
        ),
        nullable=False,
    )
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["BudgetVersion", "BudgetLineItem"]
