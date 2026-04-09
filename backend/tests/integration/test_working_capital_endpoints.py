from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest_asyncio.fixture(autouse=True)
async def _grant_working_capital_entitlement(async_session, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="working_capital",
        actor_user_id=test_user.id,
    )


@pytest.mark.asyncio
async def test_create_working_capital_snapshot(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/working-capital/snapshots",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "WC_API_Entity",
            "cash_and_equivalents": "10000",
            "accounts_receivable": "5000",
            "inventory": "2000",
            "accounts_payable": "4000",
            "currency": "USD",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "snapshot_id" in data
    assert data["intent_id"] is not None
    assert data["job_id"] is not None
    assert data["entity_name"] == "WC_API_Entity"
    assert "current_ratio" in data
    assert "working_capital" in data


@pytest.mark.asyncio
async def test_list_working_capital_snapshots(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/working-capital/snapshots",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "snapshots" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_get_latest_snapshot(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}
    entity = "Latest_WC_Entity"

    await async_client.post(
        "/api/v1/working-capital/snapshots",
        headers=headers,
        json={
            "period_year": 2025,
            "period_month": 6,
            "entity_name": entity,
            "cash_and_equivalents": "50000",
            "accounts_payable": "20000",
            "currency": "USD",
        },
    )

    response = await async_client.get(
        f"/api/v1/working-capital/snapshots/latest/{entity}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity_name"] == entity
    assert data["period_year"] == 2025


@pytest.mark.asyncio
async def test_working_capital_requires_auth(async_client: AsyncClient):
    r = await async_client.get("/api/v1/working-capital/snapshots")
    assert r.status_code == 401

