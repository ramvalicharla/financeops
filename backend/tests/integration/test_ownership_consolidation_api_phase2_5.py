from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ownership_structure_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/ownership/structures",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "ownership_structure_code": "GROUP_MAIN",
            "ownership_structure_name": "Group Main",
            "hierarchy_scope_ref": "scope-main",
            "ownership_basis_type": "equity_percentage",
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert response.status_code == 401
