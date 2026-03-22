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


def _run_request_payload(asset_code: str = "FAR-END-001") -> dict:
    return {
        "period_year": 2026,
        "period_month": 3,
        "assets": [
            {
                "asset_code": asset_code,
                "description": "Endpoint asset",
                "entity_id": "ENT-EP",
                "asset_class": "equipment",
                "asset_currency": "USD",
                "reporting_currency": "USD",
                "capitalization_date": "2026-01-01",
                "in_service_date": "2026-01-01",
                "capitalized_amount_asset_currency": "1200.000000",
                "depreciation_method": "straight_line",
                "useful_life_months": 12,
                "residual_value_reporting_currency": "200.000000",
                "rate_mode": "month_end_locked",
                "source_acquisition_reference": f"SRC-{asset_code}",
                "source_reference_id": "00000000-0000-0000-0000-00000000f801",
                "impairments": [],
                "disposals": [],
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
            "correlation_id": "corr-far-end",
        }
    )


@pytest.mark.asyncio
async def test_fixed_assets_run_status_and_results_endpoints(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    stub_temporal = _StubTemporalClient()
    with patch(
        "financeops.api.v1.fixed_assets.get_temporal_client",
        new=AsyncMock(return_value=stub_temporal),
    ):
        response = await async_client.post(
            "/api/v1/fixed-assets/run",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json=_run_request_payload(),
        )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "accepted"
    assert stub_temporal.started

    run_id = payload["run_id"]
    status_response = await async_client.get(
        f"/api/v1/fixed-assets/run/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert status_response.status_code == 200

    results_response = await async_client.get(
        f"/api/v1/fixed-assets/results/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results_response.status_code == 200
    assert results_response.json()["data"]["count"] == 0


@pytest.mark.asyncio
async def test_fixed_assets_module_specific_token_rejects_mismatch(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
) -> None:
    response = await async_client.post(
        "/api/v1/fixed-assets/run",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": _token(
                tenant_id=str(test_user.tenant_id),
                module_code="prepaid",
                decision="allow",
            ),
        },
        json=_run_request_payload("FAR-TOKEN-MISMATCH"),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_fixed_assets_invalid_control_plane_token_is_rejected(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/fixed-assets/run",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "invalid.token.value",
        },
        json=_run_request_payload("FAR-TOKEN-INVALID"),
    )
    assert response.status_code == 401

