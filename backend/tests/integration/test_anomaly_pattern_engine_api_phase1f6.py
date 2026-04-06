from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    ensure_tenant_context,
    seed_active_anomaly_configuration,
    seed_control_plane_for_anomaly,
    seed_identity_user,
    seed_upstream_for_anomaly,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/anomaly-engine/runs",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
            "source_trend_run_ids": [],
            "source_risk_run_ids": [],
            "source_reconciliation_session_ids": [],
        },
    )
    assert response.status_code in {400, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_module_enablement(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/anomaly-engine/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
            "source_trend_run_ids": [],
            "source_risk_run_ids": [],
            "source_reconciliation_session_ids": [],
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_rbac_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/anomaly-engine/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
            "source_trend_run_ids": [],
            "source_risk_run_ids": [],
            "source_reconciliation_session_ids": [],
        },
    )
    assert response.status_code in {400, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_endpoint_denies_wrong_tenant_access(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()
    await seed_identity_user(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        email="anomaly_b@example.com",
    )
    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    upstream = await seed_upstream_for_anomaly(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(async_session)
    created = await service.create_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=user_b,
    )

    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.post(
        f"/api/v1/anomaly-engine/runs/{created['run_id']}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_anomaly_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_anomaly(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    upstream = await seed_upstream_for_anomaly(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        effective_from=date(2026, 1, 1),
    )

    create = await async_client.post(
        "/api/v1/anomaly-engine/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [upstream["metric_run_id"]],
            "source_variance_run_ids": [upstream["metric_run_id"]],
            "source_trend_run_ids": [upstream["metric_run_id"]],
            "source_risk_run_ids": [upstream["risk_run_id"]],
            "source_reconciliation_session_ids": [],
        },
    )
    assert create.status_code == 201
    run_id = create.json()["data"]["run_id"]

    execute = await async_client.post(
        f"/api/v1/anomaly-engine/runs/{run_id}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert execute.status_code == 200
    payload = execute.json()["data"]
    result_count = payload.get("result_count")
    if result_count is None and isinstance(payload.get("data"), dict):
        result_count = payload["data"].get("result_count")
    assert (result_count or 0) >= 1
    executed_run_id = payload.get("run_id") or payload.get("data", {}).get("run_id")
    assert executed_run_id is not None

    get_run = await async_client.get(
        f"/api/v1/anomaly-engine/runs/{executed_run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert get_run.status_code == 200
    assert get_run.json()["data"]["status"] == "completed"

    results = await async_client.get(
        f"/api/v1/anomaly-engine/runs/{executed_run_id}/results",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results.status_code == 200
    result_rows = results.json()["data"]
    assert isinstance(result_rows, list)
    assert len(result_rows) >= 1

    signals = await async_client.get(
        f"/api/v1/anomaly-engine/runs/{executed_run_id}/signals",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert signals.status_code == 200

    rollforwards = await async_client.get(
        f"/api/v1/anomaly-engine/runs/{executed_run_id}/rollforwards",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert rollforwards.status_code == 200

    evidence = await async_client.get(
        f"/api/v1/anomaly-engine/runs/{executed_run_id}/evidence",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert evidence.status_code == 200

