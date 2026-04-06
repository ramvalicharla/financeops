from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest_asyncio.fixture(autouse=True)
async def _grant_consolidation_entitlement(async_session, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="consolidation",
        actor_user_id=test_user.id,
    )
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditWriter


def _uuid(value: str) -> UUID:
    return UUID(value)


async def _seed_snapshot_for_endpoint(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    entity_id: UUID,
) -> NormalizedFinancialSnapshot:
    snapshot = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "endpoint-src",
        },
        values={
            "entity_id": entity_id,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "endpoint-src",
            "supersedes_snapshot_id": None,
            "correlation_id": "corr-endpoint-snapshot",
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot.id),
            "account_code": "4000",
            "local_amount": "10.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot.id,
            "account_code": "4000",
            "local_amount": Decimal("10.000000"),
            "currency": "USD",
            "ic_reference": None,
            "counterparty_entity": None,
            "transaction_date": None,
            "ic_account_class": None,
            "correlation_id": "corr-endpoint-line",
        },
    )
    return snapshot


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


@pytest.mark.asyncio
async def test_consolidation_run_status_results_and_export_endpoints(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_access_token: str,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000801")
    snapshot = await _seed_snapshot_for_endpoint(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
    )
    stub_temporal = _StubTemporalClient()

    with patch(
        "financeops.api.v1.consolidation.get_temporal_client",
        new=AsyncMock(return_value=stub_temporal),
    ):
        run_response = await async_client.post(
            "/api/v1/consolidation/run",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json={
                "period_year": 2026,
                "period_month": 3,
                "parent_currency": "USD",
                "rate_mode": "daily",
                "entity_snapshots": [
                    {"entity_id": str(entity_id), "snapshot_id": str(snapshot.id)},
                ],
            },
        )
    assert run_response.status_code == 202
    run_payload = run_response.json()["data"]
    run_id = run_payload["run_id"]
    assert run_payload["status"] == "accepted"
    assert stub_temporal.started

    status_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] in {"accepted", "running", "completed", "failed"}

    results_response = await async_client.get(
        f"/api/v1/consolidation/results/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results_response.status_code == 200
    assert results_response.json()["data"]["count"] == 0

    ic_response = await async_client.get(
        f"/api/v1/consolidation/ic-differences/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert ic_response.status_code == 200
    assert ic_response.json()["data"]["count"] == 0

    export_response = await async_client.get(
        f"/api/v1/consolidation/export/{run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "X-Export-Checksum" in export_response.headers
    assert export_response.content


@pytest.mark.asyncio
async def test_consolidation_run_endpoint_validates_duplicates(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_access_token: str,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000802")
    snapshot = await _seed_snapshot_for_endpoint(
        async_session,
        tenant_id=test_tenant.id,
        entity_id=entity_id,
    )
    response = await async_client.post(
        "/api/v1/consolidation/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "rate_mode": "daily",
            "entity_snapshots": [
                {"entity_id": str(entity_id), "snapshot_id": str(snapshot.id)},
                {"entity_id": str(entity_id), "snapshot_id": str(snapshot.id)},
            ],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_consolidation_endpoints_require_auth(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/consolidation/run",
        json={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "rate_mode": "daily",
            "entity_snapshots": [],
        },
    )
    assert response.status_code == 401

