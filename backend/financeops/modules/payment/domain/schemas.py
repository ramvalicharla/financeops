from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from financeops.modules.payment.domain.enums import BillingCycle, PaymentProvider


class PaymentProviderResult(BaseModel):
    success: bool
    provider_id: str | None
    raw_response: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None


class ProviderSelection(BaseModel):
    billing_country: str
    override: PaymentProvider | None = None


class ProrationResult(BaseModel):
    credit_amount: Decimal
    debit_amount: Decimal
    net_adjustment: Decimal
    currency: str


class SubscriptionCreateRequest(BaseModel):
    tenant_id: str
    customer_id: str
    plan_id: str
    billing_cycle: BillingCycle
    trial_days: int
    metadata: dict[str, Any]
