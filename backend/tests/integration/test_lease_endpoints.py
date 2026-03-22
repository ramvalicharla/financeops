from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


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


def _run_request_payload(lease_number: str = "LEASE-END-001") -> dict:
    return {
        "reporting_currency": "USD",
        "rate_mode": "daily",
        "leases": [
            {
                "lease_number": lease_number,
                "counterparty_id": "CP-END-1",
                "lease_currency": "USD",
                "commencement_date": "2026-01-01",
                "end_date": "2026-03-31",
                "payment_frequency": "monthly",
                "initial_discount_rate": "0.120000",
                "discount_rate_source": "policy",
                "discount_rate_reference_date": "2026-01-01",
                "discount_rate_policy_code": "LSE-RATE",
                "initial_measurement_basis": "present_value",
                "source_lease_reference": f"SRC-{lease_number}",
                "policy_code": "ASC842",
                "policy_version": "v1",
                "payments": [
                    {
                        "payment_date": "2026-01-31",
                        "payment_amount_lease_currency": "100.000000",
                        "payment_type": "fixed",
                        "payment_sequence": 1,
                    }
                ],
                "modifications": [],
                "impairments": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_lease_run_status_and_results_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    stub_temporal = _StubTemporalClient()

    with patch(
        "financeops.api.v1.lease.get_temporal_client",
        new=AsyncMock(return_value=stub_temporal),
    ):
        response = await async_client.post(
            "/api/v1/lease/run",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json=_run_request_payload(),
        )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "accepted"
    assert stub_temporal.started

    run_id = payload["run_id"]

    status_response = await async_client.get(
        f"/api/v1/lease/run/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert status_response.status_code == 200

    results_response = await async_client.get(
        f"/api/v1/lease/results/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results_response.status_code == 200
    assert results_response.json()["data"]["liability_count"] == 0


@pytest.mark.asyncio
async def test_lease_run_endpoint_validates_duplicate_lease_numbers(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    payload = {
        "reporting_currency": "USD",
        "rate_mode": "daily",
        "leases": [
            _run_request_payload("LEASE-DUP-001")["leases"][0],
            _run_request_payload("LEASE-DUP-001")["leases"][0],
        ],
    }
    response = await async_client.post(
        "/api/v1/lease/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_lease_endpoints_require_auth(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/lease/run",
        json=_run_request_payload(),
    )
    assert response.status_code == 401

