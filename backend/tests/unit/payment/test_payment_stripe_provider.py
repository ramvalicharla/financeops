from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.payment.domain.enums import BillingCycle
from financeops.modules.payment.infrastructure.providers import stripe as stripe_module
from financeops.modules.payment.infrastructure.providers.stripe import StripePaymentProvider


class _FakeStripeObject:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def to_dict_recursive(self) -> dict[str, object]:
        return dict(self._payload)


@pytest.mark.asyncio
async def test_stripe_create_customer_success(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StripePaymentProvider(api_key="sk_test")

    def fake_create(**kwargs):
        assert kwargs["email"] == "user@example.com"
        return _FakeStripeObject({"id": "cus_123", "email": kwargs["email"]})

    monkeypatch.setattr(stripe_module.stripe.Customer, "create", fake_create)

    result = await provider.create_customer(
        tenant_id="tenant_1",
        email="user@example.com",
        name="User",
        metadata={"idempotency_key": "idem_1"},
    )

    assert result.success is True
    assert result.provider_id == "cus_123"
    assert result.error_code is None


@pytest.mark.asyncio
async def test_stripe_create_top_up_uses_smallest_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StripePaymentProvider(api_key="sk_test")
    captured: dict[str, object] = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeStripeObject({"id": "pi_123"})

    monkeypatch.setattr(stripe_module.stripe.PaymentIntent, "create", fake_create)

    result = await provider.create_top_up_charge(
        customer_id="cus_123",
        amount=Decimal("12.34"),
        currency="USD",
        credits=250,
        metadata={"idempotency_key": "idem_topup"},
    )

    assert result.success is True
    assert result.provider_id == "pi_123"
    assert captured["amount"] == 1234
    assert captured["currency"] == "usd"


@pytest.mark.asyncio
async def test_stripe_verify_webhook_true_and_false(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StripePaymentProvider(api_key="sk_test")

    def ok_construct_event(**kwargs):
        return {"id": "evt_1"}

    monkeypatch.setattr(stripe_module.stripe.Webhook, "construct_event", ok_construct_event)
    assert await provider.verify_webhook(b"{}", "sig", "secret") is True

    def fail_construct_event(**kwargs):
        raise ValueError("invalid")

    monkeypatch.setattr(stripe_module.stripe.Webhook, "construct_event", fail_construct_event)
    assert await provider.verify_webhook(b"{}", "sig", "secret") is False


@pytest.mark.asyncio
async def test_stripe_parse_webhook_event_maps_canonical_type() -> None:
    provider = StripePaymentProvider(api_key="sk_test")
    canonical, normalized = await provider.parse_webhook_event(
        {
            "id": "evt_123",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"invoice_id": "in_123"}},
        }
    )

    assert canonical == "invoice.paid"
    assert normalized["provider_event_id"] == "evt_123"


@pytest.mark.asyncio
async def test_stripe_create_invoice_handles_sdk_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StripePaymentProvider(api_key="sk_test")

    def fail_create(**kwargs):
        raise stripe_module.stripe.StripeError("boom")

    monkeypatch.setattr(stripe_module.stripe.Invoice, "create", fail_create)

    result = await provider.create_invoice(
        customer_id="cus_123",
        line_items=[],
        metadata={},
    )

    assert result.success is False
    assert result.error_code == "stripe_error"
