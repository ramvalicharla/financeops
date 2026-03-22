from __future__ import annotations

from httpx import AsyncClient

import pytest

from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan, create_subscription


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgrade_creates_proration_record(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    plan_from = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="99.00",
    )
    plan_to = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.ENTERPRISE,
        billing_cycle=BillingCycle.MONTHLY,
        price="499.00",
    )
    subscription = await create_subscription(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_id=plan_from.id,
    )

    response = await async_client.post(
        "/api/v1/billing/subscriptions/upgrade",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": "idem-plan-upgrade",
        },
        json={
            "subscription_id": str(subscription.id),
            "to_plan_id": str(plan_to.id),
            "prorate": True,
        },
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert "proration_record_id" in body
    assert body["currency"] == "USD"

