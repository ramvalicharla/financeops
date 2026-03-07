from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_control_plane_token_rejected(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/platform/modules/finance-exec-probe",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_code": "revenue",
            "resource_type": "revenue_run",
            "action": "execute",
            "execution_mode": "internal",
            "request_fingerprint": "rf-missing-token",
            "resource_id": "run-1",
            "context_scope": {},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_control_plane_token_rejected(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/platform/modules/finance-exec-probe",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "invalid.token",
        },
        json={
            "module_code": "revenue",
            "resource_type": "revenue_run",
            "action": "execute",
            "execution_mode": "internal",
            "request_fingerprint": "rf-invalid-token",
            "resource_id": "run-1",
            "context_scope": {},
        },
    )
    assert response.status_code == 401
