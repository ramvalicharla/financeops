from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from financeops.db.models.payment import BillingPlan, TenantSubscription
from financeops.modules.payment.domain.enums import (
    BillingCycle,
    OnboardingMode,
    PaymentProvider,
    PlanTier,
    SubscriptionStatus,
)
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.services.audit_writer import AuditWriter


class DummyPaymentProvider:
    async def create_customer(self, tenant_id: str, email: str, name: str, metadata: dict) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=f"cust_{tenant_id}", raw_response={"id": f"cust_{tenant_id}"})

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        billing_cycle: BillingCycle,
        trial_days: int,
        metadata: dict,
    ) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=f"sub_{plan_id}", raw_response={"id": f"sub_{plan_id}"})

    async def upgrade_subscription(self, subscription_id: str, new_plan_id: str, prorate: bool) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=subscription_id, raw_response={"id": subscription_id})

    async def cancel_subscription(self, subscription_id: str, cancel_at_period_end: bool) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=subscription_id, raw_response={"id": subscription_id})

    async def reactivate_subscription(self, subscription_id: str) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=subscription_id, raw_response={"id": subscription_id})

    async def create_invoice(self, customer_id: str, line_items: list[dict], metadata: dict) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=f"inv_{customer_id}", raw_response={"id": f"inv_{customer_id}"})

    async def pay_invoice(self, invoice_id: str, payment_method_id: str) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=invoice_id, raw_response={"id": invoice_id})

    async def create_payment_method(self, customer_id: str, payment_method_token: str) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=f"pm_{payment_method_token}", raw_response={"id": f"pm_{payment_method_token}"})

    async def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=payment_method_id, raw_response={"id": payment_method_id})

    async def create_top_up_charge(
        self,
        customer_id: str,
        amount: Decimal,
        currency: str,
        credits: int,
        metadata: dict,
    ) -> PaymentProviderResult:
        return PaymentProviderResult(success=True, provider_id=f"topup_{credits}", raw_response={"id": f"topup_{credits}"})

    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        return True

    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]:
        provider_event_type = str(payload.get("type") or payload.get("event") or "invoice.paid")
        canonical_map = {
            "invoice.payment_succeeded": "invoice.paid",
            "invoice.paid": "invoice.paid",
            "invoice.payment_failed": "invoice.payment_failed",
            "payment_intent.succeeded": "payment.succeeded",
            "payment.failed": "payment.failed",
            "customer.subscription.updated": "subscription.updated",
            "customer.subscription.deleted": "subscription.cancelled",
        }
        canonical = canonical_map.get(provider_event_type, "invoice.paid")
        if "data" in payload:
            obj = payload.get("data", {}).get("object", {})
        else:
            obj = payload.get("payload", {})
        return canonical, {
            "provider_event_id": str(payload.get("id", "evt_1")),
            "provider_event_type": provider_event_type,
            "object": obj,
        }

    async def get_billing_portal_url(self, customer_id: str, return_url: str) -> str:
        return f"{return_url}?customer={customer_id}"


async def create_plan(*, async_session, tenant_id: uuid.UUID, plan_tier: PlanTier, billing_cycle: BillingCycle, price: str) -> BillingPlan:
    return await AuditWriter.insert_financial_record(
        async_session,
        model_class=BillingPlan,
        tenant_id=tenant_id,
        record_data={
            "plan_tier": plan_tier.value,
            "billing_cycle": billing_cycle.value,
            "price": price,
        },
        values={
            "plan_tier": plan_tier.value,
            "billing_cycle": billing_cycle.value,
            "base_price_inr": Decimal(price),
            "base_price_usd": Decimal(price),
            "included_credits": 1000,
            "max_entities": 5,
            "max_connectors": 5,
            "max_users": 10,
            "modules_enabled": {"payment": True},
            "trial_days": 14,
            "annual_discount_pct": Decimal("10.00"),
            "is_active": True,
            "valid_from": datetime.now(UTC).date(),
            "valid_until": None,
        },
    )


async def create_subscription(
    *,
    async_session,
    tenant_id: uuid.UUID,
    plan_id: uuid.UUID,
    provider: PaymentProvider = PaymentProvider.STRIPE,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> TenantSubscription:
    today = datetime.now(UTC).date()
    suffix = uuid.uuid4().hex[:8]
    return await AuditWriter.insert_financial_record(
        async_session,
        model_class=TenantSubscription,
        tenant_id=tenant_id,
        record_data={
            "plan_id": str(plan_id),
            "provider": provider.value,
            "provider_subscription_id": f"prov_sub_{suffix}",
            "status": status.value,
        },
        values={
            "plan_id": plan_id,
            "provider": provider.value,
            "provider_subscription_id": f"prov_sub_{suffix}",
            "provider_customer_id": f"prov_cus_{suffix}",
            "status": status.value,
            "billing_cycle": BillingCycle.MONTHLY.value,
            "current_period_start": today,
            "current_period_end": today + timedelta(days=30),
            "trial_start": None,
            "trial_end": None,
            "cancelled_at": None,
            "cancel_at_period_end": False,
            "onboarding_mode": OnboardingMode.SELF_SERVE.value,
            "billing_country": "US",
            "billing_currency": "USD",
            "metadata_json": {},
        },
    )
