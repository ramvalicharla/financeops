from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_control_plane_token_allows_browser_billing_route(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {test_access_token}",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_missing_control_plane_token_reaches_erp_entitlement_gate(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/fixed-assets/run/00000000-0000-0000-0000-000000000000",
        headers={
            "Authorization": f"Bearer {test_access_token}",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"].endswith("entitlement_not_configured")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_control_plane_token_reaches_mis_entitlement_gate(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/mis/templates",
        headers={
            "Authorization": f"Bearer {test_access_token}",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"].endswith("entitlement_not_configured")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_control_plane_token_reaches_revenue_entitlement_gate(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/revenue/run/00000000-0000-0000-0000-000000000000",
        headers={
            "Authorization": f"Bearer {test_access_token}",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"].endswith("entitlement_not_configured")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_control_plane_token_does_not_override_user_plane_mis_access(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/mis/templates",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "invalid.token",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"].endswith("entitlement_not_configured")
