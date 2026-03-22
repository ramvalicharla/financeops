from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from financeops.modules.payment.domain.enums import (
    BillingCycle,
    CreditTransactionType,
    InvoiceStatus,
    OnboardingMode,
    PaymentProvider,
    PlanTier,
    SubscriptionStatus,
)


class PaymentModuleModelCatalog(BaseModel):
    providers: list[PaymentProvider] = [PaymentProvider.STRIPE, PaymentProvider.RAZORPAY]
    billing_cycles: list[BillingCycle] = [BillingCycle.MONTHLY, BillingCycle.ANNUAL]
    subscription_statuses: list[SubscriptionStatus] = [
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.GRACE_PERIOD,
        SubscriptionStatus.SUSPENDED,
        SubscriptionStatus.CANCELLED,
        SubscriptionStatus.INCOMPLETE,
    ]
    invoice_statuses: list[InvoiceStatus] = [
        InvoiceStatus.DRAFT,
        InvoiceStatus.OPEN,
        InvoiceStatus.PAID,
        InvoiceStatus.VOID,
        InvoiceStatus.UNCOLLECTIBLE,
    ]
    credit_types: list[CreditTransactionType] = [
        CreditTransactionType.PLAN_ALLOCATION,
        CreditTransactionType.TOP_UP_PURCHASE,
        CreditTransactionType.CONSUMPTION,
        CreditTransactionType.EXPIRY,
        CreditTransactionType.REFUND,
        CreditTransactionType.ADJUSTMENT,
    ]
    plan_tiers: list[PlanTier] = [PlanTier.STARTER, PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE]
    onboarding_modes: list[OnboardingMode] = [OnboardingMode.SELF_SERVE, OnboardingMode.SALES_ASSISTED]


class MoneyAmount(BaseModel):
    amount: Decimal
    currency: str


class WebhookParseResult(BaseModel):
    canonical_event_type: str
    normalized_data: dict[str, Any]
