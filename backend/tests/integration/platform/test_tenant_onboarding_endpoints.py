from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_onboarding_endpoint(async_client: AsyncClient, test_access_token: str, test_user) -> None:
    response = await async_client.post(
        "/api/v1/platform/tenants/onboard",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "tenant_code": f"TEN-{uuid.uuid4().hex[:8]}",
            "display_name": "Tenant Onboard Endpoint",
            "country_code": "US",
            "region": "us-east-1",
            "billing_tier": "pro",
            "package_code": f"PKG-{uuid.uuid4().hex[:8]}",
            "admin_user_id": str(test_user.id),
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["onboarding_status"] == "completed"
    assert payload["workflow_id"].startswith("tenant-onboarding-")
