from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reporting_currency_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/fx/reporting-currencies",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "reporting_currency_code": "USD",
            "reporting_currency_name": "US Dollar",
            "reporting_scope_type": "organisation",
            "reporting_scope_ref": str(uuid.uuid4()),
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert response.status_code == 401

