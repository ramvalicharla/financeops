from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hierarchy_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/consolidation/hierarchies",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "hierarchy_code": "group_main",
            "hierarchy_name": "Group Main",
            "hierarchy_type": "legal",
            "effective_from": "2026-01-01",
            "status": "candidate",
            "nodes": [],
        },
    )
    assert response.status_code == 403

