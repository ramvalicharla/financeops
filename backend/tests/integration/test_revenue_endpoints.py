from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest_asyncio.fixture(autouse=True)
async def _grant_revenue_entitlement(async_session, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="revenue",
        actor_user_id=test_user.id,
    )


class _StubTemporalClient:
    def __init__(self) -> None:
        self.started: list[dict[str, str]] = []

    async def start_workflow(self, workflow_run, payload, **kwargs):  # type: ignore[no-untyped-def]
        self.started.append(
            {
                "workflow": getattr(workflow_run, "__qualname__", ""),
                "run_id": payload.run_id,
                "tenant_id": payload.tenant_id,
                "correlation_id": payload.correlation_id,
                "workflow_id": kwargs["id"],
            }
        )
        return None


def _run_request_payload(contract_number: str = "REV-END-001") -> dict:
    return {
        "reporting_currency": "USD",
        "rate_mode": "daily",
        "contracts": [
            {
                "contract_number": contract_number,
                "customer_id": "CUST-END-1",
                "contract_currency": "USD",
                "contract_start_date": "2026-01-01",
                "contract_end_date": "2026-03-31",
                "total_contract_value": "300.000000",
                "source_contract_reference": f"SRC-{contract_number}",
                "policy_code": "ASC606",
                "policy_version": "v1",
                "performance_obligations": [
                    {
                        "obligation_code": "OBL-1",
                        "description": "Endpoint obligation",
                        "standalone_selling_price": "300.000000",
                        "allocation_basis": "ssp",
                        "recognition_method": "straight_line",
                    }
                ],
                "contract_line_items": [
                    {
                        "line_code": "LINE-1",
                        "obligation_code": "OBL-1",
                        "line_amount": "300.000000",
                        "line_currency": "USD",
                        "recognition_method": "straight_line",
                        "recognition_start_date": "2026-01-01",
                        "recognition_end_date": "2026-03-31",
                    }
                ],
                "modifications": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_revenue_run_status_and_results_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    stub_temporal = _StubTemporalClient()

    with patch(
        "financeops.temporal.client.get_temporal_client",
        new=AsyncMock(return_value=stub_temporal),
    ):
        response = await async_client.post(
            "/api/v1/revenue/run",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json=_run_request_payload(),
        )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "accepted"
    assert stub_temporal.started

    run_id = payload["run_id"]

    status_response = await async_client.get(
        f"/api/v1/revenue/run/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] in {"accepted", "running", "completed", "failed"}

    results_response = await async_client.get(
        f"/api/v1/revenue/results/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results_response.status_code == 200
    assert results_response.json()["data"]["count"] == 0


@pytest.mark.asyncio
async def test_revenue_run_endpoint_validates_duplicate_contract_numbers(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    payload = {
        "reporting_currency": "USD",
        "rate_mode": "daily",
        "contracts": [
            _run_request_payload("REV-DUP-001")["contracts"][0],
            _run_request_payload("REV-DUP-001")["contracts"][0],
        ],
    }
    response = await async_client.post(
        "/api/v1/revenue/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_revenue_endpoints_require_auth(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/revenue/run",
        json=_run_request_payload(),
    )
    assert response.status_code == 401

