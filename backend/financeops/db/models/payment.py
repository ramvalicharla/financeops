from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase, utc_now


class BillingPlan(FinancialBase):
    __tablename__ = "billing_plans"
    __table_args__ = (
        CheckConstraint("plan_tier IN ('starter','professional','enterprise')", name="ck_billing_plans_tier"),
        CheckConstraint("billing_cycle IN ('monthly','annual')", name="ck_billing_plans_cycle"),
        CheckConstraint(
            "pricing_type IS NULL OR pricing_type IN ('flat','tiered','usage','hybrid')",
            name="ck_billing_plans_pricing_type",
        ),
        CheckConstraint("annual_discount_pct >= 0", name="ck_billing_plans_discount_non_negative"),
        Index("idx_billing_plans_tenant_active", "tenant_id", "is_active", "created_at"),
    )

    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    pricing_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    base_price_inr: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    base_price_usd: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    included_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    max_entities: Mapped[int] = mapped_column(Integer, nullable=False)
    max_connectors: Mapped[int] = mapped_column(Integer, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    modules_enabled: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_discount_pct: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class TenantSubscription(FinancialBase):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('trialing','active','past_due','grace_period','suspended','cancelled','incomplete')",
            name="ck_tenant_subscriptions_status",
        ),
        CheckConstraint("billing_cycle IN ('monthly','annual')", name="ck_tenant_subscriptions_cycle"),
        CheckConstraint("onboarding_mode IN ('self_serve','sales_assisted')", name="ck_tenant_subscriptions_onboarding_mode"),
        Index("idx_tenant_subscriptions_current", "tenant_id", "status", "current_period_end", "created_at"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    current_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    current_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    trial_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    trial_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trial_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    onboarding_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_country: Mapped[str] = mapped_column(String(2), nullable=False)
    billing_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class SubscriptionEvent(FinancialBase):
    __tablename__ = "subscription_events"
    __table_args__ = (
        Index("idx_subscription_events_subscription", "tenant_id", "subscription_id", "created_at"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    to_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class BillingInvoice(FinancialBase):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        CheckConstraint("status IN ('draft','open','paid','void','uncollectible')", name="ck_billing_invoices_status"),
        Index("idx_billing_invoices_tenant", "tenant_id", "subscription_id", "status", "created_at"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_invoice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credits_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invoice_pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)


class PaymentMethod(FinancialBase):
    __tablename__ = "payment_methods"
    __table_args__ = (
        Index("idx_payment_methods_tenant", "tenant_id", "provider", "is_default", "created_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_method_id: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    billing_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CreditLedger(FinancialBase):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('plan_allocation','top_up_purchase','consumption','expiry','refund','adjustment')",
            name="ck_credit_ledger_transaction_type",
        ),
        Index("idx_credit_ledger_tenant_created", "tenant_id", "created_at"),
    )

    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    credits_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CreditTopUp(FinancialBase):
    __tablename__ = "credit_top_ups"
    __table_args__ = (
        CheckConstraint("status IN ('pending','completed','failed','refunded')", name="ck_credit_top_ups_status"),
        Index("idx_credit_top_ups_tenant", "tenant_id", "status", "created_at"),
        UniqueConstraint("tenant_id", "provider_payment_id", name="uq_credit_top_ups_provider_payment"),
    )

    credits_purchased: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_charged: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class WebhookEvent(FinancialBase):
    __tablename__ = "webhook_events"
    # Keep webhook_events unpartitioned for now. Our idempotency guarantee depends on
    # global uniqueness across (tenant_id, provider, provider_event_id), and monthly
    # partitioning by created_at would conflict with that guarantee in PostgreSQL.
    __table_args__ = (
        Index("idx_webhook_events_tenant", "tenant_id", "provider", "processed", "created_at"),
        Index("idx_webhook_events_created_at", "created_at"),
        UniqueConstraint("tenant_id", "provider", "provider_event_id", name="uq_webhook_events_provider_event"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class GracePeriodLog(FinancialBase):
    __tablename__ = "grace_period_logs"
    __table_args__ = (
        Index("idx_grace_period_logs_tenant", "tenant_id", "subscription_id", "grace_period_end", "created_at"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grace_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProrationRecord(FinancialBase):
    __tablename__ = "proration_records"
    __table_args__ = (
        Index("idx_proration_records_tenant", "tenant_id", "subscription_id", "proration_date", "created_at"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proration_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    net_adjustment: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    applied_to_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )


class BillingPayment(FinancialBase):
    __tablename__ = "billing_payments"
    __table_args__ = (
        CheckConstraint(
            "payment_status IN ('pending','succeeded','failed','refunded')",
            name="ck_billing_payments_status",
        ),
        Index("idx_billing_payments_tenant_invoice", "tenant_id", "invoice_id", "created_at"),
        UniqueConstraint("tenant_id", "provider_reference", name="uq_billing_payments_provider_ref"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class BillingEntitlement(FinancialBase):
    __tablename__ = "billing_entitlements"
    __table_args__ = (
        CheckConstraint(
            "access_type IN ('boolean','limit','quota')",
            name="ck_billing_entitlements_access_type",
        ),
        Index("idx_billing_entitlements_plan_feature", "tenant_id", "plan_id", "feature_name", "created_at"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    access_type: Mapped[str] = mapped_column(String(16), nullable=False)
    limit_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TenantEntitlement(FinancialBase):
    __tablename__ = "billing_tenant_entitlements"
    __table_args__ = (
        CheckConstraint(
            "source IN ('plan','override')",
            name="ck_billing_tenant_entitlements_source",
        ),
        Index("idx_billing_tenant_entitlements_feature", "tenant_id", "feature_name", "created_at"),
    )

    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    access_type: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="plan")
    source_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BillingUsageEvent(FinancialBase):
    __tablename__ = "billing_usage_events"
    __table_args__ = (
        Index("idx_billing_usage_events_feature_time", "tenant_id", "feature_name", "event_time"),
    )

    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    usage_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class BillingUsageAggregate(FinancialBase):
    __tablename__ = "billing_usage_aggregates"
    __table_args__ = (
        Index("idx_billing_usage_aggregates_period", "tenant_id", "feature_name", "period_start", "period_end"),
    )

    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_usage: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_usage_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
