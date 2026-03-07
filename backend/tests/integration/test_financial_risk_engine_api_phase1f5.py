from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.financial_risk_phase1f5_helpers import (
    build_financial_risk_service,
    ensure_tenant_context,
    seed_active_risk_configuration,
    seed_control_plane_for_financial_risk,
    seed_identity_user,
    seed_upstream_ratio_run,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/financial-risk/runs",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_module_enablement(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_financial_risk(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/financial-risk/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
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
    await seed_control_plane_for_financial_risk(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/financial-risk/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_variance_run_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 403


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
        email="risk_b@example.com",
    )
    await seed_control_plane_for_financial_risk(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    upstream = await seed_upstream_ratio_run(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(async_session)
    created = await service.create_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=user_b,
    )

    await seed_control_plane_for_financial_risk(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.post(
        f"/api/v1/financial-risk/runs/{created['run_id']}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_financial_risk_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_financial_risk(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    upstream = await seed_upstream_ratio_run(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        effective_from=date(2026, 1, 1),
    )

    create = await async_client.post(
        "/api/v1/financial-risk/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [upstream["ratio_run_id"]],
            "source_variance_run_ids": [upstream["ratio_run_id"]],
            "source_trend_run_ids": [upstream["ratio_run_id"]],
            "source_reconciliation_session_ids": [],
        },
    )
    assert create.status_code == 201
    run_id = create.json()["run_id"]

    execute = await async_client.post(
        f"/api/v1/financial-risk/runs/{run_id}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert execute.status_code == 200
    executed = execute.json()
    assert executed["result_count"] >= 1
    executed_run_id = executed["run_id"]

    summary = await async_client.get(
        f"/api/v1/financial-risk/runs/{executed_run_id}/summary",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert summary.status_code == 200
    assert summary.json()["result_count"] >= 1

    results = await async_client.get(
        f"/api/v1/financial-risk/runs/{executed_run_id}/results",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert results.status_code == 200
    assert isinstance(results.json(), list)

    signals = await async_client.get(
        f"/api/v1/financial-risk/runs/{executed_run_id}/signals",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert signals.status_code == 200

    rollforwards = await async_client.get(
        f"/api/v1/financial-risk/runs/{executed_run_id}/rollforwards",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert rollforwards.status_code == 200

    evidence = await async_client.get(
        f"/api/v1/financial-risk/runs/{executed_run_id}/evidence",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert evidence.status_code == 200
