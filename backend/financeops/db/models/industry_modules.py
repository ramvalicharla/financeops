from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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


class FinanceModule(Base):
    __tablename__ = "finance_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_name", name="uq_finance_modules_tenant_module"),
        Index("ix_finance_modules_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    module_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="DISABLED")
    configuration_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
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


class IndustryLease(Base):
    __tablename__ = "industry_leases"
    __table_args__ = (
        Index("ix_industry_leases_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_industry_leases_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lease_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    lease_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    lease_payment: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    lease_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryLeaseSchedule(Base):
    __tablename__ = "industry_lease_schedules"
    __table_args__ = (
        UniqueConstraint("lease_id", "period_number", name="uq_industry_lease_schedule_period"),
        Index("ix_industry_lease_schedules_tenant_lease", "tenant_id", "lease_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_leases.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_liability: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    interest_expense: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    lease_payment: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    closing_liability: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    rou_asset_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    depreciation: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryContract(Base):
    __tablename__ = "industry_contracts"
    __table_args__ = (
        Index("ix_industry_contracts_tenant_entity", "tenant_id", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryPerformanceObligation(Base):
    __tablename__ = "industry_performance_obligations"
    __table_args__ = (
        Index("ix_industry_obligations_tenant_contract", "tenant_id", "contract_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    obligation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    allocation_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryRevenueSchedule(Base):
    __tablename__ = "industry_revenue_schedules"
    __table_args__ = (
        UniqueConstraint(
            "obligation_id",
            "period_number",
            name="uq_industry_revenue_schedules_period",
        ),
        Index("ix_industry_revenue_schedules_tenant_obligation", "tenant_id", "obligation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_performance_obligations.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    recognition_date: Mapped[date] = mapped_column(Date, nullable=False)
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryFixedAsset(Base):
    __tablename__ = "industry_fixed_assets"
    __table_args__ = (
        Index("ix_industry_fixed_assets_tenant_entity", "tenant_id", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_name: Mapped[str] = mapped_column(String(256), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    useful_life_years: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(16), nullable=False)
    residual_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryAssetSchedule(Base):
    __tablename__ = "industry_asset_schedules"
    __table_args__ = (
        UniqueConstraint("asset_id", "period_number", name="uq_industry_asset_schedules_period"),
        Index("ix_industry_asset_schedules_tenant_asset", "tenant_id", "asset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_fixed_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    depreciation: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_book_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryPrepaidSchedule(Base):
    __tablename__ = "industry_prepaid_schedules"
    __table_args__ = (
        UniqueConstraint(
            "schedule_batch_id",
            "period_number",
            name="uq_industry_prepaid_schedules_batch_period",
        ),
        Index("ix_industry_prepaid_schedules_tenant_batch", "tenant_id", "schedule_batch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schedule_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prepaid_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    amortization_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    remaining_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryAccrualSchedule(Base):
    __tablename__ = "industry_accrual_schedules"
    __table_args__ = (
        UniqueConstraint(
            "schedule_batch_id",
            "period_number",
            name="uq_industry_accrual_schedules_batch_period",
        ),
        Index("ix_industry_accrual_schedules_tenant_batch", "tenant_id", "schedule_batch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schedule_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accrual_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    accrual_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    remaining_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustrySubscription(Base):
    __tablename__ = "industry_subscriptions"
    __table_args__ = (
        Index("ix_industry_subscriptions_tenant_entity", "tenant_id", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    billing_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    revenue_recognition_method: Mapped[str] = mapped_column(String(32), nullable=False, server_default="STRAIGHT_LINE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryBillingSchedule(Base):
    __tablename__ = "industry_billing_schedules"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "period_number",
            name="uq_industry_billing_schedules_period",
        ),
        Index("ix_industry_billing_schedules_tenant_subscription", "tenant_id", "subscription_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    billing_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    deferred_revenue_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class IndustryJournalLink(Base):
    __tablename__ = "industry_journal_links"
    __table_args__ = (
        Index("ix_industry_journal_links_tenant_reference", "tenant_id", "module_name", "module_record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    module_name: Mapped[str] = mapped_column(String(64), nullable=False)
    module_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "FinanceModule",
    "IndustryAccrualSchedule",
    "IndustryAssetSchedule",
    "IndustryBillingSchedule",
    "IndustryContract",
    "IndustryFixedAsset",
    "IndustryJournalLink",
    "IndustryLease",
    "IndustryLeaseSchedule",
    "IndustryPerformanceObligation",
    "IndustryPrepaidSchedule",
    "IndustryRevenueSchedule",
    "IndustrySubscription",
]
