from __future__ import annotations

from httpx import AsyncClient

import pytest

from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan


@pytest.mark.asyncio
@pytest.mark.integration
async def test_billing_plans_endpoints_return_enveloped_payload(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
) -> None:
    plan = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="99.00",
    )

    headers = {"Authorization": f"Bearer {test_access_token}"}
    list_resp = await async_client.get("/api/v1/billing/plans", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["success"] is True
    assert len(list_resp.json()["data"]["items"]) >= 1

    get_resp = await async_client.get(f"/api/v1/billing/plans/{plan.id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["success"] is True
    assert get_resp.json()["data"]["id"] == str(plan.id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_billing_subscription_create_rejects_missing_idempotency_key(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    plan = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.PROFESSIONAL,
        billing_cycle=BillingCycle.MONTHLY,
        price="199.00",
    )
    headers = {"Authorization": f"Bearer {test_access_token}"}
    response = await async_client.post(
        "/api/v1/billing/subscriptions",
        headers=headers,
        json={
            "plan_id": str(plan.id),
            "email": "finance@example.com",
            "name": "Finance User",
            "billing_country": "US",
            "billing_currency": "USD",
            "billing_cycle": "monthly",
        },
    )
    assert response.status_code == 400
    assert response.json()["success"] is False
