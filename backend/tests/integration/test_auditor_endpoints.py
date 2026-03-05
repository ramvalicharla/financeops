from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_auditor_grant(
    async_client: AsyncClient, test_user, test_access_token: str
):
    """Finance leader can grant auditor access."""
    auditor_id = str(uuid.uuid4())
    response = await async_client.post(
        "/api/v1/auditor/grants",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "auditor_user_id": auditor_id,
            "scope": "limited",
            "allowed_modules": ["reconciliation"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "grant_id" in data
    assert data["is_active"] is True
    assert data["scope"] == "limited"


@pytest.mark.asyncio
async def test_list_auditor_grants(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/auditor/grants",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "grants" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_revoke_auditor_grant(
    async_client: AsyncClient, test_user, test_access_token: str
):
    """Revoking a grant creates a new row with is_active=False."""
    headers = {"Authorization": f"Bearer {test_access_token}"}
    auditor_id = str(uuid.uuid4())

    grant_resp = await async_client.post(
        "/api/v1/auditor/grants",
        headers=headers,
        json={"auditor_user_id": auditor_id, "scope": "full"},
    )
    assert grant_resp.status_code == 201
    grant_id = grant_resp.json()["grant_id"]

    revoke_resp = await async_client.request(
        "DELETE",
        f"/api/v1/auditor/grants/{grant_id}",
        headers=headers,
        json={"notes": "Engagement completed"},
    )
    assert revoke_resp.status_code == 200
    data = revoke_resp.json()
    assert data["is_active"] is False
    assert data["revoked_at"] is not None


@pytest.mark.asyncio
async def test_access_check_non_auditor_returns_403(
    async_client: AsyncClient, test_user, test_access_token: str
):
    """Finance leader calling the auditor access-check endpoint gets 403."""
    response = await async_client.get(
        "/api/v1/auditor/me/access-check",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_auditor_endpoints_require_auth(async_client: AsyncClient):
    for path in ["/api/v1/auditor/grants", "/api/v1/auditor/access-logs"]:
        r = await async_client.get(path)
        assert r.status_code == 401
