from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_register_creates_tenant_and_user(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
            "tenant_name": "New Corp",
            "tenant_type": "direct",
            "country": "US",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert "tenant_id" in data
    assert data["mfa_setup_required"] is True


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_tokens(
    async_client: AsyncClient, test_user
):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(
    async_client: AsyncClient, test_user
):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_accessing_protected_endpoint_without_token_returns_401(
    async_client: AsyncClient,
):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(
    async_client: AsyncClient, test_access_token: str, test_user
):
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert "tenant" in data


@pytest.mark.asyncio
async def test_refresh_token_rotation(
    async_client: AsyncClient, test_user
):
    # Login to get initial tokens
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    initial_refresh = login_resp.json()["refresh_token"]

    # Rotate
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens
    new_refresh = new_tokens["refresh_token"]
    assert new_refresh != initial_refresh

    # Old token should now be invalid
    old_refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert old_refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # After logout, refresh should fail
    retry_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert retry_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_sets_tenant_context_from_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    with patch(
        "financeops.api.v1.auth.set_tenant_context",
        new_callable=AsyncMock,
    ) as set_ctx:
        refresh_resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    assert refresh_resp.status_code == 200
    assert set_ctx.await_count == 1


@pytest.mark.asyncio
async def test_logout_sets_tenant_context_from_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    with patch(
        "financeops.api.v1.auth.set_tenant_context",
        new_callable=AsyncMock,
    ) as set_ctx:
        logout_resp = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
    assert logout_resp.status_code == 200
    assert set_ctx.await_count == 1
