from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest_asyncio.fixture(autouse=True)
async def _grant_gst_entitlement(async_session, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="gst",
        actor_user_id=test_user.id,
    )


@pytest.mark.asyncio
async def test_create_gst_return(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/gst/returns",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "GST_API_Entity",
            "gstin": "29ABCDE1234F1Z5",
            "return_type": "GSTR1",
            "taxable_value": "100000",
            "igst_amount": "18000",
            "cgst_amount": "0",
            "sgst_amount": "0",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "return_id" in data
    assert data["intent_id"]
    assert data["job_id"]
    assert data["return_type"] == "GSTR1"
    assert data["total_tax"] == "18000"


@pytest.mark.asyncio
async def test_run_gst_reconciliation(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}
    entity = "GST_Run_Entity"
    period = {"period_year": 2025, "period_month": 9}
    common = {
        "entity_name": entity,
        "gstin": "29GSTRUN1234F1Z5",
        "taxable_value": "200000",
        "igst_amount": "36000",
        "cgst_amount": "0",
        "sgst_amount": "0",
        **period,
    }

    for return_type in ("GSTR1", "GSTR3B"):
        await async_client.post(
            "/api/v1/gst/returns",
            headers=headers,
            json={**common, "return_type": return_type},
        )

    recon_resp = await async_client.post(
        "/api/v1/gst/reconcile",
        headers=headers,
        json={
            **period,
            "entity_name": entity,
            "return_type_a": "GSTR1",
            "return_type_b": "GSTR3B",
        },
    )
    assert recon_resp.status_code == 201
    data = recon_resp.json()["data"]
    assert "breaks_found" in data
    assert data["intent_id"]
    assert data["job_id"]
    assert data["breaks_found"] == 0


@pytest.mark.asyncio
async def test_list_gst_returns(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/gst/returns",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "returns" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_gst_returns_list_respects_limit(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {test_access_token}"}
    for idx in range(5):
        response = await async_client.post(
            "/api/v1/gst/returns",
            headers=headers,
            json={
                "period_year": 2025,
                "period_month": 8,
                "entity_name": f"GST_LIMIT_{idx}",
                "gstin": f"29GSTLIM{idx:04d}F1Z5",
                "return_type": "GSTR1",
                "taxable_value": "100000",
                "igst_amount": "18000",
                "cgst_amount": "0",
                "sgst_amount": "0",
            },
        )
        assert response.status_code == 201

    response = await async_client.get("/api/v1/gst/returns?limit=2", headers=headers)
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["items"]) == 2
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_gst_returns_list_respects_skip(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {test_access_token}"}
    for idx in range(5):
        response = await async_client.post(
            "/api/v1/gst/returns",
            headers=headers,
            json={
                "period_year": 2025,
                "period_month": 10,
                "entity_name": f"GST_SKIP_{idx}",
                "gstin": f"29GSTSKP{idx:04d}F1Z5",
                "return_type": "GSTR3B",
                "taxable_value": "100000",
                "igst_amount": "18000",
                "cgst_amount": "0",
                "sgst_amount": "0",
            },
        )
        assert response.status_code == 201

    response = await async_client.get("/api/v1/gst/returns?skip=3&limit=10", headers=headers)
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["items"]) == 2


@pytest.mark.asyncio
async def test_gst_endpoints_require_auth(async_client: AsyncClient):
    for path in ["/api/v1/gst/returns", "/api/v1/gst/recon-items"]:
        r = await async_client.get(path)
        assert r.status_code == 401

