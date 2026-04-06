from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _create_other_tenant_user(async_session: AsyncSession) -> IamUser:
    tenant_id = uuid.uuid4()
    tenant_payload = {
        "display_name": "Other Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(tenant_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    async_session.add(tenant)
    await async_session.flush()

    user = IamUser(
        tenant_id=tenant.id,
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Tenant User",
        role=UserRole.read_only,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.mark.asyncio
async def test_get_tenant_me(
    async_client: AsyncClient, test_access_token: str, test_tenant
):
    response = await async_client.get(
        "/api/v1/tenants/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
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
    data = response.json()["data"]
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
    data = response.json()["data"]
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
            "entity_ids": [],
        },
    )
    # finance_leader should be allowed
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["email"] == "invited@example.com"


@pytest.mark.asyncio
async def test_invite_user_rejects_platform_role_assignment(
    async_client: AsyncClient, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/tenants/me/users",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "email": "platform-escalation@example.com",
            "full_name": "Escalation Attempt",
            "role": "platform_admin",
            "entity_ids": [],
        },
    )
    assert response.status_code == 422
    assert "Platform roles cannot be assigned" in response.text


@pytest.mark.asyncio
async def test_update_user_rejects_platform_role_assignment(
    async_client: AsyncClient, test_access_token: str
):
    invite = await async_client.post(
        "/api/v1/tenants/me/users",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "email": "role-update@example.com",
            "full_name": "Role Update User",
            "role": "read_only",
            "entity_ids": [],
        },
    )
    assert invite.status_code == 201
    user_id = invite.json()["data"]["user_id"]

    response = await async_client.patch(
        f"/api/v1/tenants/me/users/{user_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"role": "platform_owner"},
    )
    assert response.status_code == 422
    assert "Platform roles cannot be assigned" in response.text


@pytest.mark.asyncio
async def test_update_user_cross_tenant_is_rejected(
    async_client: AsyncClient, async_session: AsyncSession, test_access_token: str
):
    other_user = await _create_other_tenant_user(async_session)
    response = await async_client.patch(
        f"/api/v1/tenants/me/users/{other_user.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"role": "read_only"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_cross_tenant_is_rejected(
    async_client: AsyncClient, async_session: AsyncSession, test_access_token: str
):
    other_user = await _create_other_tenant_user(async_session)
    response = await async_client.delete(
        f"/api/v1/tenants/me/users/{other_user.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 404


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
    assert response.json()["data"]["updated"] is True

    verify_resp = await async_client.get(
        "/api/v1/tenants/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert verify_resp.status_code == 200
    payload = verify_resp.json()["data"]
    assert payload["display_name"] == "Renamed Tenant"
    assert payload["timezone"] == "Asia/Kolkata"

