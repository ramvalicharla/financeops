from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ExpensePolicy(Base):
    __tablename__ = "expense_policies"
    __table_args__ = (
        Index("idx_expense_policies_tenant", "tenant_id", unique=True),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    meal_limit_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("2000"), default=Decimal("2000"))
    travel_limit_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("8000"), default=Decimal("8000"))
    receipt_required_above: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("500"), default=Decimal("500"))
    auto_approve_below: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    weekend_flag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    round_number_flag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    personal_merchant_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"
    __table_args__ = (
        CheckConstraint(
            "category IN ('meals','travel','accommodation','office_supplies','professional_fees','other')",
            name="ck_expense_claims_category",
        ),
        CheckConstraint(
            "status IN ('submitted','policy_checked','approved','rejected','gl_coded','paid','cancelled')",
            name="ck_expense_claims_status",
        ),
        CheckConstraint(
            "policy_violation_type IS NULL OR policy_violation_type IN ('none','soft_limit','hard_limit','receipt_missing','personal_merchant','duplicate','weekend','round_number')",
            name="ck_expense_claims_violation",
        ),
        Index("idx_expense_claims_tenant_user_period", "tenant_id", "submitted_by", "period"),
        Index("idx_expense_claims_tenant_status", "tenant_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(300), nullable=False)
    vendor_gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"), default="INR")
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0"))
    itc_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'submitted'"), default="submitted")
    policy_violation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    policy_violation_requires_justification: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    manager_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finance_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gl_account_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gl_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cost_centre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ExpenseApproval(Base):
    __tablename__ = "expense_approvals"
    __table_args__ = (
        CheckConstraint(
            "action IN ('approved','rejected','returned')",
            name="ck_expense_approvals_action",
        ),
        Index("idx_expense_approvals_claim", "claim_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("expense_claims.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["ExpensePolicy", "ExpenseClaim", "ExpenseApproval"]

