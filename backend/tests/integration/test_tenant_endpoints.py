from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_tenant_me(
    async_client: AsyncClient, test_access_token: str, test_tenant
):
    response = await async_client.get(
        "/api/v1/tenants/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["display_name"] == "Test Tenant"


@pytest.mark.asyncio
async def test_list_tenant_users(
    async_client: AsyncClient, test_access_token: str, test_user
):
    response = await async_client.get(
        "/api/v1/tenants/me/users",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert len(data["users"]) >= 1


@pytest.mark.asyncio
async def test_get_credits(
    async_client: AsyncClient, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/tenants/me/credits",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "balance" in data
    assert "available" in data
    assert "transactions" in data


@pytest.mark.asyncio
async def test_invite_user_requires_finance_leader(
    async_client: AsyncClient, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/tenants/me/users",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "email": "invited@example.com",
            "full_name": "Invited User",
            "role": "read_only",
            "password": "TempPass123!",
        },
    )
    # finance_leader should be allowed
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "invited@example.com"


@pytest.mark.asyncio
async def test_update_tenant_me_uses_mutation_path(
    async_client: AsyncClient, test_access_token: str
):
    response = await async_client.patch(
        "/api/v1/tenants/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "display_name": "Renamed Tenant",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 200
    assert response.json()["updated"] is True

    verify_resp = await async_client.get(
        "/api/v1/tenants/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert verify_resp.status_code == 200
    payload = verify_resp.json()
    assert payload["display_name"] == "Renamed Tenant"
    assert payload["timezone"] == "Asia/Kolkata"
