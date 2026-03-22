from __future__ import annotations

import json

from httpx import AsyncClient

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_razorpay_webhook_returns_200_and_accepts_event(
    async_client: AsyncClient,
    test_user,
    mock_payment_provider,
) -> None:
    payload = {
        "id": "evt_rzp_1",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "notes": {"tenant_id": str(test_user.tenant_id)},
                }
            }
        },
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/razorpay",
        headers={"X-Razorpay-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["accepted"] is True

