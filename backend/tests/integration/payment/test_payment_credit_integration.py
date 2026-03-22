from __future__ import annotations

from httpx import AsyncClient

import pytest

from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan, create_subscription


@pytest.mark.asyncio
@pytest.mark.integration
async def test_credit_top_up_updates_balance_and_ledger(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    idem_headers: dict[str, str],
    mock_payment_provider,
) -> None:
    plan = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="99.00",
    )
    await create_subscription(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_id=plan.id,
    )

    headers = {"Authorization": f"Bearer {test_access_token}", **idem_headers}
    top_up = await async_client.post(
        "/api/v1/billing/credits/top-up",
        headers=headers,
        json={"credits": 250, "amount": "49.00", "currency": "USD"},
    )
    assert top_up.status_code == 200
    assert top_up.json()["success"] is True

    balance = await async_client.get(
        "/api/v1/billing/credits/balance",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert balance.status_code == 200
    assert balance.json()["data"]["balance"] >= 250

    ledger = await async_client.get(
        "/api/v1/billing/credits/ledger",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert ledger.status_code == 200
    assert len(ledger.json()["data"]["items"]) >= 1

