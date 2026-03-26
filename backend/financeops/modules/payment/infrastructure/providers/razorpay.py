from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import razorpay

from financeops.config import settings
from financeops.modules.payment.domain.enums import BillingCycle
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.modules.payment.infrastructure.providers.base import AbstractPaymentProvider


_RAZORPAY_CANONICAL_EVENT_MAP: dict[str, str] = {
    "subscription.activated": "subscription.created",
    "subscription.updated": "subscription.updated",
    "subscription.cancelled": "subscription.cancelled",
    "invoice.created": "invoice.created",
    "invoice.paid": "invoice.paid",
    "invoice.payment_failed": "invoice.payment_failed",
    "payment.captured": "payment.succeeded",
    "payment.failed": "payment.failed",
    "payment.dispute.created": "dispute.created",
    "refund.created": "refund.created",
}


class RazorpayPaymentProvider(AbstractPaymentProvider):
    def __init__(self, *, key_id: str | None = None, key_secret: str | None = None) -> None:
        self._key_id = key_id or settings.RAZORPAY_KEY_ID
        self._key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self._client = razorpay.Client(auth=(self._key_id, self._key_secret))

    @staticmethod
    def _to_paise(amount: Decimal) -> int:
        quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))

    @staticmethod
    def _idempotency_receipt(metadata: dict[str, Any] | None = None) -> str | None:
        if not metadata:
            return None
        value = metadata.get("idempotency_key")
        return str(value) if value else None

    @staticmethod
    def _to_dict(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        data_attr = getattr(payload, "data", None)
        if isinstance(data_attr, dict):
            return data_attr
        return {"value": str(payload)}

    @staticmethod
    def _error_result(exc: Exception) -> PaymentProviderResult:
        return PaymentProviderResult(
            success=False,
            provider_id=None,
            raw_response={"error": str(exc)},
            error_code="razorpay_error",
            error_message=str(exc),
        )

    async def create_customer(self, tenant_id: str, email: str, name: str, metadata: dict) -> PaymentProviderResult:
        try:
            created = self._client.customer.create(
                {
                    "name": name,
                    "email": email,
                    "notes": {**metadata, "tenant_id": tenant_id},
                }
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        billing_cycle: BillingCycle,
        trial_days: int,
        metadata: dict,
    ) -> PaymentProviderResult:
        try:
            created = self._client.subscription.create(
                {
                    "plan_id": plan_id,
                    "customer_notify": 1,
                    "total_count": 12 if billing_cycle == BillingCycle.MONTHLY else 1,
                    "customer_id": customer_id,
                    "start_at": None,
                    "expire_by": None,
                    "addons": [],
                    "notes": metadata,
                    "offer_id": None,
                    "quantity": 1,
                    "remaining_count": None,
                    "schedule_change_at": None,
                    "trial_days": trial_days,
                }
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def upgrade_subscription(self, subscription_id: str, new_plan_id: str, prorate: bool) -> PaymentProviderResult:
        try:
            updated = self._client.subscription.edit(
                subscription_id,
                {
                    "plan_id": new_plan_id,
                    "schedule_change_at": "now" if prorate else "cycle_end",
                },
            )
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", subscription_id)), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def cancel_subscription(self, subscription_id: str, cancel_at_period_end: bool) -> PaymentProviderResult:
        try:
            cancelled = self._client.subscription.cancel(
                subscription_id,
                {"cancel_at_cycle_end": 1 if cancel_at_period_end else 0},
            )
            data = self._to_dict(cancelled)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", subscription_id)), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def reactivate_subscription(self, subscription_id: str) -> PaymentProviderResult:
        try:
            updated = self._client.subscription.edit(subscription_id, {"cancel_at_cycle_end": 0})
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", subscription_id)), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def create_invoice(self, customer_id: str, line_items: list[dict], metadata: dict) -> PaymentProviderResult:
        try:
            amount_total = sum(self._to_paise(Decimal(str(item.get("amount", "0")))) for item in line_items)
            created = self._client.invoice.create(
                {
                    "customer_id": customer_id,
                    "line_items": line_items,
                    "currency": str(metadata.get("currency", "INR")).upper(),
                    "amount": amount_total,
                    "description": metadata.get("description"),
                    "notes": metadata,
                }
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def pay_invoice(self, invoice_id: str, payment_method_id: str) -> PaymentProviderResult:
        try:
            paid = self._client.invoice.edit(
                invoice_id,
                {
                    "payment_method": payment_method_id,
                    "status": "paid",
                },
            )
            data = self._to_dict(paid)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", invoice_id)), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def create_payment_method(self, customer_id: str, payment_method_token: str) -> PaymentProviderResult:
        # Razorpay stores payment methods implicitly through tokenized checkout.
        payload = {
            "customer_id": customer_id,
            "payment_method_token": payment_method_token,
            "status": "tokenized",
        }
        return PaymentProviderResult(success=True, provider_id=payment_method_token, raw_response=payload)

    async def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> PaymentProviderResult:
        try:
            updated = self._client.customer.edit(customer_id, {"default_payment_method": payment_method_id})
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", customer_id)), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def create_top_up_charge(
        self,
        customer_id: str,
        amount: Decimal,
        currency: str,
        credits: int,
        metadata: dict,
    ) -> PaymentProviderResult:
        try:
            receipt = self._idempotency_receipt(metadata)
            created = self._client.order.create(
                {
                    "amount": self._to_paise(amount),
                    "currency": currency.upper(),
                    "receipt": receipt,
                    "notes": {**metadata, "customer_id": customer_id, "credits": str(credits)},
                }
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except Exception as exc:
            return self._error_result(exc)

    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]:
        event_type = str(payload.get("event", ""))
        canonical = _RAZORPAY_CANONICAL_EVENT_MAP.get(event_type, "unknown")
        normalized = {
            "provider_event_id": payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
            or payload.get("id"),
            "provider_event_type": event_type,
            "object": payload.get("payload", {}),
        }
        return canonical, normalized

    async def get_billing_portal_url(self, customer_id: str, return_url: str) -> str:
        return f"{return_url}?customer_id={customer_id}"
