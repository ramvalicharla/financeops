from __future__ import annotations

import pytest

from financeops.modules.payment.infrastructure.providers.razorpay import RazorpayPaymentProvider
from financeops.modules.payment.infrastructure.providers.stripe import StripePaymentProvider


@pytest.mark.asyncio
async def test_stripe_event_maps_to_canonical_invoice_paid() -> None:
    provider = StripePaymentProvider(api_key="sk_test")
    canonical, payload = await provider.parse_webhook_event(
        {
            "id": "evt_1",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"invoice_id": "in_1"}},
        }
    )
    assert canonical == "invoice.paid"
    assert payload["provider_event_id"] == "evt_1"


@pytest.mark.asyncio
async def test_razorpay_event_maps_to_canonical_payment_succeeded() -> None:
    provider = RazorpayPaymentProvider(key_id="rzp_test", key_secret="secret")
    canonical, payload = await provider.parse_webhook_event(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"id": "pay_123"}}},
        }
    )
    assert canonical == "payment.succeeded"
    assert payload["provider_event_id"] == "pay_123"

