from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

try:
    import stripe  # type: ignore[import-not-found]
except ModuleNotFoundError:
    class _StripeShim:
        class StripeError(Exception):
            pass

        class Customer:
            @staticmethod
            def create(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

            @staticmethod
            def modify(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class Subscription:
            @staticmethod
            def create(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

            @staticmethod
            def modify(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

            @staticmethod
            def delete(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class InvoiceItem:
            @staticmethod
            def create(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class Invoice:
            @staticmethod
            def create(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

            @staticmethod
            def pay(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class PaymentMethod:
            @staticmethod
            def attach(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

            @staticmethod
            def detach(*args, **kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class PaymentIntent:
            @staticmethod
            def create(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class Webhook:
            @staticmethod
            def construct_event(**kwargs):
                raise ModuleNotFoundError("stripe package is not installed")

        class billing_portal:
            class Session:
                @staticmethod
                def create(**kwargs):
                    raise ModuleNotFoundError("stripe package is not installed")

    stripe = _StripeShim()  # type: ignore[assignment]

from financeops.config import settings
from financeops.modules.payment.domain.enums import BillingCycle
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.modules.payment.infrastructure.providers.base import AbstractPaymentProvider


_STRIPE_CANONICAL_EVENT_MAP: dict[str, str] = {
    "customer.subscription.created": "subscription.created",
    "customer.subscription.updated": "subscription.updated",
    "customer.subscription.deleted": "subscription.cancelled",
    "customer.subscription.trial_will_end": "subscription.trial_ending",
    "invoice.created": "invoice.created",
    "invoice.payment_succeeded": "invoice.paid",
    "invoice.payment_failed": "invoice.payment_failed",
    "payment_intent.succeeded": "payment.succeeded",
    "payment_intent.payment_failed": "payment.failed",
    "payment_method.attached": "payment_method.attached",
    "payment_method.detached": "payment_method.detached",
    "charge.dispute.created": "dispute.created",
    "charge.refunded": "refund.created",
}


class StripePaymentProvider(AbstractPaymentProvider):
    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.STRIPE_SECRET_KEY
        if self._api_key:
            stripe.api_key = self._api_key

    @staticmethod
    def _idempotency_key(metadata: dict[str, Any] | None = None) -> str | None:
        if not metadata:
            return None
        value = metadata.get("idempotency_key")
        return str(value) if value else None

    @staticmethod
    def _to_smallest_unit(amount: Decimal) -> int:
        quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))

    @staticmethod
    def _to_dict(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        converter = getattr(payload, "to_dict_recursive", None)
        if callable(converter):
            result = converter()
            if isinstance(result, dict):
                return result
        data_attr = getattr(payload, "data", None)
        if isinstance(data_attr, dict):
            return data_attr
        return {"value": str(payload)}

    @staticmethod
    def _error_result(exc: Exception) -> PaymentProviderResult:
        code = getattr(exc, "code", None)
        return PaymentProviderResult(
            success=False,
            provider_id=None,
            raw_response={"error": str(exc)},
            error_code=str(code) if code else "stripe_error",
            error_message=str(exc),
        )

    async def create_customer(self, tenant_id: str, email: str, name: str, metadata: dict) -> PaymentProviderResult:
        try:
            created = stripe.Customer.create(
                email=email,
                name=name,
                metadata={**metadata, "tenant_id": tenant_id},
                idempotency_key=self._idempotency_key(metadata),
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
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
            created = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                trial_period_days=trial_days if trial_days > 0 else None,
                metadata={**metadata, "billing_cycle": billing_cycle.value},
                idempotency_key=self._idempotency_key(metadata),
            )
            data = self._to_dict(created)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def upgrade_subscription(self, subscription_id: str, new_plan_id: str, prorate: bool) -> PaymentProviderResult:
        try:
            updated = stripe.Subscription.modify(
                subscription_id,
                items=[{"price": new_plan_id}],
                proration_behavior="create_prorations" if prorate else "none",
            )
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def cancel_subscription(self, subscription_id: str, cancel_at_period_end: bool) -> PaymentProviderResult:
        try:
            if cancel_at_period_end:
                updated = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
            else:
                updated = stripe.Subscription.delete(subscription_id)
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", subscription_id)), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def reactivate_subscription(self, subscription_id: str) -> PaymentProviderResult:
        try:
            updated = stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def create_invoice(self, customer_id: str, line_items: list[dict], metadata: dict) -> PaymentProviderResult:
        try:
            for line in line_items:
                amount = Decimal(str(line.get("amount", "0")))
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    amount=self._to_smallest_unit(amount),
                    currency=str(line.get("currency", "usd")).lower(),
                    description=line.get("description"),
                )
            invoice = stripe.Invoice.create(
                customer=customer_id,
                metadata=metadata,
                idempotency_key=self._idempotency_key(metadata),
            )
            data = self._to_dict(invoice)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def pay_invoice(self, invoice_id: str, payment_method_id: str) -> PaymentProviderResult:
        try:
            paid = stripe.Invoice.pay(invoice_id, payment_method=payment_method_id)
            data = self._to_dict(paid)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", invoice_id)), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def create_payment_method(self, customer_id: str, payment_method_token: str) -> PaymentProviderResult:
        try:
            attached = stripe.PaymentMethod.attach(payment_method_token, customer=customer_id)
            data = self._to_dict(attached)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> PaymentProviderResult:
        try:
            updated = stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )
            data = self._to_dict(updated)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", customer_id)), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def detach_payment_method(self, payment_method_id: str) -> PaymentProviderResult:
        try:
            detached = stripe.PaymentMethod.detach(payment_method_id)
            data = self._to_dict(detached)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id", payment_method_id)), raw_response=data)
        except stripe.StripeError as exc:
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
            payment_intent = stripe.PaymentIntent.create(
                customer=customer_id,
                amount=self._to_smallest_unit(amount),
                currency=currency.lower(),
                metadata={**metadata, "credits": str(credits)},
                idempotency_key=self._idempotency_key(metadata),
            )
            data = self._to_dict(payment_intent)
            return PaymentProviderResult(success=True, provider_id=str(data.get("id")), raw_response=data)
        except stripe.StripeError as exc:
            return self._error_result(exc)

    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        try:
            stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=secret)
            return True
        except stripe.StripeError:
            return False
        except ValueError:
            return False

    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]:
        event_type = str(payload.get("type", ""))
        canonical = _STRIPE_CANONICAL_EVENT_MAP.get(event_type, "unknown")
        event_object = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
        normalized = {
            "provider_event_id": payload.get("id"),
            "provider_event_type": event_type,
            "object": event_object,
        }
        return canonical, normalized

    async def get_billing_portal_url(self, customer_id: str, return_url: str) -> str:
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        data = self._to_dict(session)
        return str(data.get("url", return_url))
