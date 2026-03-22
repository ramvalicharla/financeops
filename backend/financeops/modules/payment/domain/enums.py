from __future__ import annotations

from enum import Enum


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class CreditTransactionType(str, Enum):
    PLAN_ALLOCATION = "plan_allocation"
    TOP_UP_PURCHASE = "top_up_purchase"
    CONSUMPTION = "consumption"
    EXPIRY = "expiry"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class PlanTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class OnboardingMode(str, Enum):
    SELF_SERVE = "self_serve"
    SALES_ASSISTED = "sales_assisted"
