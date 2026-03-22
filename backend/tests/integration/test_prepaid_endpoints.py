from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from financeops.platform.services.enforcement.context_token import issue_context_token


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


def _run_request_payload(prepaid_code: str = "PPD-END-001") -> dict:
    return {
        "period_year": 2026,
        "period_month": 3,
        "prepaids": [
            {
                "prepaid_code": prepaid_code,
                "description": "Endpoint prepaid",
                "prepaid_currency": "USD",
                "reporting_currency": "USD",
                "term_start_date": "2026-01-01",
                "term_end_date": "2026-03-31",
                "base_amount_contract_currency": "300.000000",
                "period_frequency": "monthly",
                "pattern_type": "straight_line",
                "rate_mode": "month_end_locked",
                "source_expense_reference": f"SRC-{prepaid_code}",
                "source_reference_id": "00000000-0000-0000-0000-000000012201",
                "adjustments": [],
            }
        ],
    }


def _token(*, tenant_id: str, module_code: str, decision: str = "allow") -> str:
    issued_at = datetime.now(UTC)
    return issue_context_token(
        {
            "tenant_id": tenant_id,
            "module_code": module_code,
            "decision": decision,
            "policy_snapshot_version": 1,
            "quota_check_id": "quota-check",
            "isolation_route_version": 1,
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
            "correlation_id": "corr-prepaid-end",
        }
    )


@pytest.mark.asyncio
async def test_prepaid_run_status_and_results_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    stub_temporal = _StubTemporalClient()

    with patch(
        "financeops.api.v1.prepaid.get_temporal_client",
        new=AsyncMock(return_value=stub_temporal),
    ):
        response = await async_client.post(
            "/api/v1/prepaid/run",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json=_run_request_payload(),
        )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "accepted"
    assert stub_temporal.started

    run_id = payload["run_id"]

    status_response = await async_client.get(
        f"/api/v1/prepaid/run/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert status_response.status_code == 200

    results_response = await async_client.get(
        f"/api/v1/prepaid/results/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results_response.status_code == 200
    assert results_response.json()["data"]["count"] == 0


@pytest.mark.asyncio
async def test_prepaid_run_endpoint_validates_duplicate_codes(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    payload = {
        "period_year": 2026,
        "period_month": 3,
        "prepaids": [
            _run_request_payload("PPD-DUP-001")["prepaids"][0],
            _run_request_payload("PPD-DUP-001")["prepaids"][0],
        ],
    }
    response = await async_client.post(
        "/api/v1/prepaid/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_prepaid_module_specific_token_rejects_mismatch(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
) -> None:
    response = await async_client.post(
        "/api/v1/prepaid/run",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": _token(
                tenant_id=str(test_user.tenant_id),
                module_code="revenue",
                decision="allow",
            ),
        },
        json=_run_request_payload("PPD-TOKEN-MISMATCH"),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_prepaid_token_with_deny_decision_is_rejected(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
) -> None:
    response = await async_client.post(
        "/api/v1/prepaid/run",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": _token(
                tenant_id=str(test_user.tenant_id),
                module_code="prepaid",
                decision="deny",
            ),
        },
        json=_run_request_payload("PPD-TOKEN-DENY"),
    )
    assert response.status_code == 401

