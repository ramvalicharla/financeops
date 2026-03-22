from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

import pytest

from financeops.modules.payment.domain.enums import BillingCycle
from financeops.modules.payment.infrastructure.providers import razorpay as razorpay_module
from financeops.modules.payment.infrastructure.providers.razorpay import RazorpayPaymentProvider


class _Resource:
    def __init__(self) -> None:
        self._next_create: dict[str, object] = {"id": "default"}
        self._next_edit: dict[str, object] = {"id": "default"}
        self._next_cancel: dict[str, object] = {"id": "default"}
        self.calls: list[tuple[str, tuple, dict]] = []

    def create(self, payload: dict):
        self.calls.append(("create", tuple(), payload))
        return dict(self._next_create)

    def edit(self, resource_id: str, payload: dict):
        self.calls.append(("edit", (resource_id,), payload))
        return dict(self._next_edit)

    def cancel(self, resource_id: str, payload: dict | None = None):
        self.calls.append(("cancel", (resource_id,), payload or {}))
        return dict(self._next_cancel)


class _FakeClient:
    def __init__(self, auth: tuple[str, str]) -> None:
        self.auth = auth
        self.customer = _Resource()
        self.subscription = _Resource()
        self.invoice = _Resource()
        self.order = _Resource()
        self.payment = _Resource()


@pytest.mark.asyncio
async def test_razorpay_create_customer_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(razorpay_module.razorpay, "Client", _FakeClient)
    provider = RazorpayPaymentProvider(key_id="key", key_secret="secret")
    provider._client.customer._next_create = {"id": "cust_123"}

    result = await provider.create_customer(
        tenant_id="tenant_1",
        email="user@example.com",
        name="User",
        metadata={"source": "test"},
    )

    assert result.success is True
    assert result.provider_id == "cust_123"


@pytest.mark.asyncio
async def test_razorpay_create_subscription_and_topup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(razorpay_module.razorpay, "Client", _FakeClient)
    provider = RazorpayPaymentProvider(key_id="key", key_secret="secret")
    provider._client.subscription._next_create = {"id": "sub_123"}
    provider._client.order._next_create = {"id": "order_123"}

    subscription = await provider.create_subscription(
        customer_id="cust_1",
        plan_id="plan_1",
        billing_cycle=BillingCycle.MONTHLY,
        trial_days=7,
        metadata={"source": "test"},
    )
    top_up = await provider.create_top_up_charge(
        customer_id="cust_1",
        amount=Decimal("12.34"),
        currency="INR",
        credits=100,
        metadata={"idempotency_key": "idem_123"},
    )

    assert subscription.success is True
    assert subscription.provider_id == "sub_123"
    assert top_up.success is True
    assert top_up.provider_id == "order_123"
    create_call = provider._client.order.calls[-1]
    assert create_call[2]["amount"] == 1234
    assert create_call[2]["receipt"] == "idem_123"


@pytest.mark.asyncio
async def test_razorpay_verify_webhook_and_parse() -> None:
    provider = RazorpayPaymentProvider(key_id="key", key_secret="secret")
    payload = b'{"event":"payment.captured"}'
    secret = "secret"
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert await provider.verify_webhook(payload, signature, secret) is True

    canonical, normalized = await provider.parse_webhook_event(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"id": "pay_1"}}},
        }
    )
    assert canonical == "payment.succeeded"
    assert normalized["provider_event_id"] == "pay_1"


@pytest.mark.asyncio
async def test_razorpay_error_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(razorpay_module.razorpay, "Client", _FakeClient)
    provider = RazorpayPaymentProvider(key_id="key", key_secret="secret")

    def raise_create(payload: dict):
        raise RuntimeError("boom")

    provider._client.invoice.create = raise_create

    result = await provider.create_invoice(
        customer_id="cust_1",
        line_items=[],
        metadata={},
    )

    assert result.success is False
    assert result.error_code == "razorpay_error"
