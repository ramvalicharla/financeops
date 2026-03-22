from __future__ import annotations

import json

from httpx import AsyncClient

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_returns_200_and_accepts_event(
    async_client: AsyncClient,
    test_user,
    mock_payment_provider,
) -> None:
    payload = {
        "id": "evt_stripe_1",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"metadata": {"tenant_id": str(test_user.tenant_id)}}},
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["accepted"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_returns_200_on_processing_error(
    async_client: AsyncClient,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*args, **kwargs):
        raise RuntimeError("handler boom")

    monkeypatch.setattr(
        "financeops.modules.payment.api.webhooks.WebhookService.handle_webhook",
        _raise,
    )
    payload = {
        "id": "evt_stripe_2",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"metadata": {"tenant_id": str(test_user.tenant_id)}}},
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["accepted"] is True
    assert body["processed"] is False

