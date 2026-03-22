from __future__ import annotations

import uuid

from httpx import AsyncClient

import pytest

from financeops.api import deps as api_deps
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan


class _InMemoryRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        _ = ttl
        self._store[key] = value


@pytest.mark.asyncio
@pytest.mark.integration
async def test_subscription_create_replays_cached_response_for_same_idempotency_key(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    plan = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="99.00",
    )
    redis = _InMemoryRedis()
    original_pool = api_deps._redis_pool
    api_deps._redis_pool = redis
    try:
        idem_key = f"idem_{uuid.uuid4().hex}"
        headers = {
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": idem_key,
        }
        payload = {
            "plan_id": str(plan.id),
            "email": "billing@example.com",
            "name": "Billing User",
            "billing_country": "US",
            "billing_currency": "USD",
            "billing_cycle": "monthly",
        }
        first = await async_client.post("/api/v1/billing/subscriptions", headers=headers, json=payload)
        second = await async_client.post("/api/v1/billing/subscriptions", headers=headers, json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.headers.get("Idempotency-Replayed") == "true"
        assert first.json()["data"] == second.json()["data"]
    finally:
        api_deps._redis_pool = original_pool

