from __future__ import annotations

from httpx import AsyncClient

import pytest

from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan


@pytest.mark.asyncio
@pytest.mark.integration
async def test_subscription_create_cancel_reactivate_flow(
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
    auth = {"Authorization": f"Bearer {test_access_token}"}

    create = await async_client.post(
        "/api/v1/billing/subscriptions",
        headers={**auth, "Idempotency-Key": "idem-sub-create"},
        json={
            "plan_id": str(plan.id),
            "email": "owner@example.com",
            "name": "Owner",
            "billing_country": "US",
            "billing_currency": "USD",
            "billing_cycle": "monthly",
        },
    )
    assert create.status_code == 200
    created_id = create.json()["data"]["subscription_id"]

    current = await async_client.get("/api/v1/billing/subscriptions/current", headers=auth)
    assert current.status_code == 200
    assert current.json()["data"]["item"]["id"] == created_id

    cancel = await async_client.post(
        "/api/v1/billing/subscriptions/cancel",
        headers={**auth, "Idempotency-Key": "idem-sub-cancel"},
        json={"subscription_id": created_id, "cancel_at_period_end": False},
    )
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] == "cancelled"

    cancelled_current = await async_client.get("/api/v1/billing/subscriptions/current", headers=auth)
    cancelled_id = cancelled_current.json()["data"]["item"]["id"]
    reactivate = await async_client.post(
        "/api/v1/billing/subscriptions/reactivate",
        headers={**auth, "Idempotency-Key": "idem-sub-reactivate"},
        json={"subscription_id": cancelled_id},
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["data"]["status"] == "active"

