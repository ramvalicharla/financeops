from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200_without_auth(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["version"] == "1.1.0"


@pytest.mark.asyncio
async def test_deep_health_requires_auth(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health/deep")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deep_health_returns_200_with_auth(
    async_client: AsyncClient, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/health/deep",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] in ("ok", "degraded")
    assert "checks" in data
    assert "db" in data["checks"]

