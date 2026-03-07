from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class _StubTemporalClient:
    async def execute_workflow(self, workflow_run, payload, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        workflow_name = getattr(workflow_run, "__qualname__", "")
        if workflow_name.startswith("FxFetchWorkflow.run"):
            return {
                "fetch_run_id": "stub-fetch-id",
                "status": "success",
                "base_currency": payload.base_currency,
                "quote_currency": payload.quote_currency,
                "rate_date": payload.rate_date or "2026-03-06",
                "selected_rate": "83.100000",
                "selected_source": "provider_consensus",
                "selection_method": "median_of_available_provider_quotes",
                "fallback_used": False,
                "providers": [],
            }
        return {
            "period_year": payload.period_year,
            "period_month": payload.period_month,
            "base_currency": payload.base_currency,
            "quote_currency": payload.quote_currency,
            "selected_rate": "83.500000",
            "selected_source": "manual_monthly",
            "lines": [],
            "count": 0,
            "lock_rate_id": "stub-lock-id",
        }


class _StubTemporalClientDegraded:
    async def execute_workflow(self, workflow_run, payload, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        workflow_name = getattr(workflow_run, "__qualname__", "")
        if workflow_name.startswith("FxFetchWorkflow.run"):
            return {
                "fetch_run_id": "stub-fetch-degraded-id",
                "status": "degraded",
                "base_currency": payload.base_currency,
                "quote_currency": payload.quote_currency,
                "rate_date": payload.rate_date or "2026-03-06",
                "selected_rate": "83.150000",
                "selected_source": "provider_consensus",
                "selection_method": "median_of_available_provider_quotes",
                "fallback_used": False,
                "providers": [
                    {"provider": "ecb", "status": "ok", "rate": "83.100000", "rate_date": "2026-03-06", "error": None},
                    {"provider": "frankfurter", "status": "ok", "rate": "83.200000", "rate_date": "2026-03-06", "error": None},
                    {
                        "provider": "open_exchange_rates",
                        "status": "error",
                        "rate": None,
                        "rate_date": None,
                        "error": "OPEN_EXCHANGE_RATES_API_KEY not configured",
                    },
                    {
                        "provider": "exchange_rate_api",
                        "status": "error",
                        "rate": None,
                        "rate_date": None,
                        "error": "EXCHANGE_RATE_API_KEY not configured",
                    },
                ],
            }
        return {
            "period_year": payload.period_year,
            "period_month": payload.period_month,
            "base_currency": payload.base_currency,
            "quote_currency": payload.quote_currency,
            "selected_rate": "83.500000",
            "selected_source": "manual_monthly",
            "lines": [],
            "count": 0,
            "lock_rate_id": "stub-lock-id",
        }


@pytest.mark.asyncio
async def test_fx_fetch_live_endpoint_uses_temporal(
    async_client: AsyncClient,
    test_access_token: str,
):
    with patch(
        "financeops.api.v1.fx_rates.get_temporal_client",
        new=AsyncMock(return_value=_StubTemporalClient()),
    ):
        response = await async_client.post(
            "/api/v1/fx/fetch-live",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json={"base_currency": "USD", "quote_currency": "INR", "rate_date": "2026-03-06"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["selected_source"] == "provider_consensus"


@pytest.mark.asyncio
async def test_fx_fetch_live_endpoint_surfaces_degraded_status(
    async_client: AsyncClient,
    test_access_token: str,
):
    with patch(
        "financeops.api.v1.fx_rates.get_temporal_client",
        new=AsyncMock(return_value=_StubTemporalClientDegraded()),
    ):
        response = await async_client.post(
            "/api/v1/fx/fetch-live",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json={"base_currency": "USD", "quote_currency": "INR", "rate_date": "2026-03-06"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "degraded"
    assert len(data["providers"]) == 4
    assert data["providers"][2]["error"] == "OPEN_EXCHANGE_RATES_API_KEY not configured"
    assert data["providers"][3]["error"] == "EXCHANGE_RATE_API_KEY not configured"


@pytest.mark.asyncio
async def test_manual_monthly_create_and_list(
    async_client: AsyncClient,
    test_access_token: str,
):
    create_response = await async_client.post(
        "/api/v1/fx/manual-monthly",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2026,
            "period_month": 3,
            "base_currency": "USD",
            "quote_currency": "NTD",
            "rate": "31.250000",
            "reason": "Month-end approved profile",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["count"] == 1
    assert payload["rates"][0]["quote_currency"] == "TWD"

    list_response = await async_client.get(
        "/api/v1/fx/manual-monthly",
        headers={"Authorization": f"Bearer {test_access_token}"},
        params={"period_year": 2026, "period_month": 3, "base_currency": "USD", "quote_currency": "TWD"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 1


@pytest.mark.asyncio
async def test_convert_daily_uses_selected_rate(
    async_client: AsyncClient,
    test_access_token: str,
):
    # Seed manual monthly so conversion can resolve selection without live provider fetch.
    seed_response = await async_client.post(
        "/api/v1/fx/manual-monthly",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2026,
            "period_month": 4,
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "80.000000",
            "reason": "Conversion test seed",
        },
    )
    assert seed_response.status_code == 201

    response = await async_client.post(
        "/api/v1/fx/convert-daily",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "lines": [
                {
                    "reference": "txn-1",
                    "transaction_date": "2026-04-15",
                    "amount": "10.00",
                    "base_currency": "USD",
                    "quote_currency": "INR",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["lines"][0]["applied_rate"] == "80.000000"
    assert data["lines"][0]["converted_amount"] == "800.00"


@pytest.mark.asyncio
async def test_apply_month_end_endpoint_uses_temporal(
    async_client: AsyncClient,
    test_access_token: str,
):
    with patch(
        "financeops.api.v1.fx_rates.get_temporal_client",
        new=AsyncMock(return_value=_StubTemporalClient()),
    ):
        response = await async_client.post(
            "/api/v1/fx/apply-month-end",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json={
                "period_year": 2026,
                "period_month": 3,
                "base_currency": "USD",
                "quote_currency": "INR",
                "approval_reason": "Close sign-off",
                "lines": [{"reference": "line-1", "amount": "100.00"}],
            },
        )
    assert response.status_code == 201
    assert response.json()["lock_rate_id"] == "stub-lock-id"


@pytest.mark.asyncio
async def test_variance_endpoint_persists_result(
    async_client: AsyncClient,
    test_access_token: str,
):
    response = await async_client.post(
        "/api/v1/fx/variance",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2026,
            "period_month": 3,
            "base_currency": "USD",
            "quote_currency": "INR",
            "expected_difference": "1000.000000",
            "actual_difference": "980.000000",
            "entity_name": "Entity A",
            "notes": "IC explained by timing",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["fx_variance"] == "-20.000000"


@pytest.mark.asyncio
async def test_fx_endpoints_require_auth(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/fx/manual-monthly",
    )
    assert response.status_code == 401
