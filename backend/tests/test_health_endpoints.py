from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_health_root_returns_all_checks(async_client) -> None:
    """GET /health includes all sub-system checks."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "checks" in data
    for key in ["database", "redis", "ai", "queues", "temporal", "workers"]:
        assert key in data["checks"], f"Missing check: {key}"


@pytest.mark.asyncio
async def test_health_ai_does_not_leak_api_keys(async_client) -> None:
    """GET /health/ai never returns API key values."""
    response = await async_client.get("/health/ai")
    assert response.status_code == 200
    body = response.text
    assert "sk-" not in body
    assert "Bearer" not in body


@pytest.mark.asyncio
async def test_health_queues_structure(async_client) -> None:
    """GET /health/queues returns queue depth structure."""
    response = await async_client.get("/health/queues")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "queues" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_health_temporal_does_not_fail_platform(monkeypatch, async_client) -> None:
    """Temporal down does not force overall unhealthy."""
    monkeypatch.setattr(
        "financeops.api.v1.health._check_temporal",
        AsyncMock(return_value={"status": "down", "address": "x", "namespace": "default"}),
    )
    response = await async_client.get("/health")
    payload = response.json()["data"]
    assert payload["checks"]["temporal"] == "down"
    assert payload["health_status"] != "unhealthy"


@pytest.mark.asyncio
async def test_health_ai_status_shape(async_client) -> None:
    """AI health payload has required keys."""
    response = await async_client.get("/health/ai")
    data = response.json()["data"]
    for key in ["status", "ollama", "anthropic", "openai", "fallback_available"]:
        assert key in data


@pytest.mark.asyncio
async def test_health_temporal_shape(async_client) -> None:
    """Temporal health payload includes address and namespace."""
    response = await async_client.get("/health/temporal")
    data = response.json()["data"]
    assert "status" in data
    assert "address" in data
    assert "namespace" in data


@pytest.mark.asyncio
async def test_health_workers_shape(async_client) -> None:
    """Workers health payload includes worker count."""
    response = await async_client.get("/health/workers")
    data = response.json()["data"]
    assert "status" in data
    assert "active_workers" in data


@pytest.mark.asyncio
async def test_health_root_includes_version(async_client) -> None:
    """Root health includes app version."""
    response = await async_client.get("/health")
    data = response.json()["data"]
    assert "version" in data


@pytest.mark.asyncio
async def test_health_root_includes_timestamp(async_client) -> None:
    """Root health includes timestamp."""
    response = await async_client.get("/health")
    data = response.json()["data"]
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_deep_health_requires_auth(async_client) -> None:
    """Deep health endpoint requires auth."""
    response = await async_client.get("/api/v1/health/deep")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deep_health_with_auth_contains_checks(async_client, test_access_token: str) -> None:
    """Deep health includes checks for authenticated requests."""
    response = await async_client.get(
        "/api/v1/health/deep",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "checks" in data
    assert "db" in data["checks"]
