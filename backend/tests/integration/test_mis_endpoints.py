from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_mis_template(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/mis/templates",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "name": "Monthly P&L Template",
            "entity_name": "Corp A",
            "template_data": {"sheets": ["P&L", "Balance Sheet"], "columns": []},
            "is_master": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "template_id" in data
    assert data["name"] == "Monthly P&L Template"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_list_mis_templates_authenticated(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/mis/templates",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_create_mis_template_unauthenticated(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/mis/templates",
        json={
            "name": "Test",
            "entity_name": "X",
            "template_data": {},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_mis_upload(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/mis/uploads",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "entity_name": "Corp A",
            "period_year": 2025,
            "period_month": 3,
            "file_name": "march_report.xlsx",
            "file_hash": "a" * 64,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "upload_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_mis_template_not_found(
    async_client: AsyncClient, test_user, test_access_token: str
):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await async_client.get(
        f"/api/v1/mis/templates/{fake_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 404
