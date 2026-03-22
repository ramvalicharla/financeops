from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_gl_entry(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/recon/gl-entries",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "Recon_API_Entity",
            "account_code": "1000",
            "account_name": "Cash",
            "debit_amount": "1000.00",
            "credit_amount": "0.00",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "entry_id" in data
    assert data["account_code"] == "1000"


@pytest.mark.asyncio
async def test_import_tb_row(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/recon/tb-rows",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "Recon_API_Entity",
            "account_code": "1000",
            "account_name": "Cash",
            "opening_balance": "0",
            "period_debit": "1000",
            "period_credit": "0",
            "closing_balance": "1000",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "row_id" in data
    assert data["closing_balance"] == "1000"


@pytest.mark.asyncio
async def test_run_reconciliation_returns_result(
    async_client: AsyncClient, test_user, test_access_token: str
):
    """GL net == TB closing → no breaks."""
    entity = "API_Recon_Run"
    headers = {"Authorization": f"Bearer {test_access_token}"}

    await async_client.post(
        "/api/v1/recon/gl-entries",
        headers=headers,
        json={
            "period_year": 2025, "period_month": 8,
            "entity_name": entity, "account_code": "2000",
            "account_name": "AR", "debit_amount": "500", "credit_amount": "0",
        },
    )
    await async_client.post(
        "/api/v1/recon/tb-rows",
        headers=headers,
        json={
            "period_year": 2025, "period_month": 8,
            "entity_name": entity, "account_code": "2000",
            "account_name": "AR", "opening_balance": "0",
            "period_debit": "500", "period_credit": "0", "closing_balance": "500",
        },
    )
    response = await async_client.post(
        "/api/v1/recon/run",
        headers=headers,
        json={"period_year": 2025, "period_month": 8, "entity_name": entity},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "breaks_found" in data
    assert data["breaks_found"] == 0


@pytest.mark.asyncio
async def test_list_gl_entries(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/recon/gl-entries",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "entries" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_recon_endpoints_require_auth(async_client: AsyncClient):
    for path in ["/api/v1/recon/gl-entries", "/api/v1/recon/tb-rows", "/api/v1/recon/items"]:
        r = await async_client.get(path)
        assert r.status_code == 401

