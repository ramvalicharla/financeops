from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_monthend_checklist(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/monthend/",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "ME_API_Entity",
            "add_default_tasks": True,
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "checklist_id" in data
    assert data["status"] == "open"
    assert data["entity_name"] == "ME_API_Entity"


@pytest.mark.asyncio
async def test_get_monthend_checklist_with_tasks(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}

    create_resp = await async_client.post(
        "/api/v1/monthend/",
        headers=headers,
        json={
            "period_year": 2025,
            "period_month": 4,
            "entity_name": "ME_Get_Entity",
            "add_default_tasks": True,
        },
    )
    checklist_id = create_resp.json()["data"]["checklist_id"]

    get_resp = await async_client.get(
        f"/api/v1/monthend/{checklist_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["checklist_id"] == checklist_id
    assert len(data["tasks"]) == 10


@pytest.mark.asyncio
async def test_update_task_status(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}

    create_resp = await async_client.post(
        "/api/v1/monthend/",
        headers=headers,
        json={
            "period_year": 2025,
            "period_month": 5,
            "entity_name": "ME_Update_Entity",
            "add_default_tasks": True,
        },
    )
    checklist_id = create_resp.json()["data"]["checklist_id"]

    get_resp = await async_client.get(
        f"/api/v1/monthend/{checklist_id}",
        headers=headers,
    )
    task_id = get_resp.json()["data"]["tasks"][0]["task_id"]

    patch_resp = await async_client.patch(
        f"/api/v1/monthend/{checklist_id}/tasks/{task_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_close_monthend_checklist(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}

    create_resp = await async_client.post(
        "/api/v1/monthend/",
        headers=headers,
        json={
            "period_year": 2025,
            "period_month": 6,
            "entity_name": "ME_Close_Entity",
            "add_default_tasks": False,
        },
    )
    checklist_id = create_resp.json()["data"]["checklist_id"]

    close_resp = await async_client.post(
        f"/api/v1/monthend/{checklist_id}/close",
        headers=headers,
        json={"notes": "Period closed successfully"},
    )
    assert close_resp.status_code == 201
    data = close_resp.json()["data"]
    assert data["status"] == "closed"
    assert data["closed_at"] is not None


@pytest.mark.asyncio
async def test_monthend_requires_auth(async_client: AsyncClient):
    r = await async_client.get("/api/v1/monthend/")
    assert r.status_code == 401

