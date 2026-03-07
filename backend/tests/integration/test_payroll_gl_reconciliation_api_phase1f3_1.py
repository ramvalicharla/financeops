from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    build_payroll_gl_reconciliation_service,
    ensure_tenant_context,
    seed_control_plane_for_payroll_gl_reconciliation,
    seed_finalized_normalization_pair,
    seed_identity_user,
    seed_mapping_and_rule,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/payroll-gl-reconciliation/runs",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "payroll_run_id": str(uuid.uuid4()),
            "gl_run_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
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
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/payroll-gl-reconciliation/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "payroll_run_id": str(uuid.uuid4()),
            "gl_run_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
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
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/payroll-gl-reconciliation/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "payroll_run_id": str(uuid.uuid4()),
            "gl_run_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
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
        email="paygl_b@example.com",
    )
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    pair = await seed_finalized_normalization_pair(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        effective_from=date(2026, 1, 1),
    )
    service_b = build_payroll_gl_reconciliation_service(async_session)
    run_b = await service_b.create_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=user_b,
    )

    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.post(
        f"/api/v1/payroll-gl-reconciliation/runs/{run_b['run_id']}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lines_endpoint_returns_only_tenant_scoped_data(
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
        email="paygl_lines_b@example.com",
    )
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    pair = await seed_finalized_normalization_pair(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        effective_from=date(2026, 1, 1),
    )
    service_b = build_payroll_gl_reconciliation_service(async_session)
    created = await service_b.create_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=user_b,
    )
    await service_b.execute_run(
        tenant_id=tenant_b,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=user_b,
    )
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.get(
        f"/api/v1/payroll-gl-reconciliation/runs/{created['run_id']}/lines",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_payroll_gl_reconciliation_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_payroll_gl_reconciliation(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, test_user.tenant_id)
    pair = await seed_finalized_normalization_pair(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        effective_from=date(2026, 1, 1),
    )

    create = await async_client.post(
        "/api/v1/payroll-gl-reconciliation/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "payroll_run_id": pair["payroll_run_id"],
            "gl_run_id": pair["gl_run_id"],
            "reporting_period": "2026-01-31",
        },
    )
    assert create.status_code == 201
    create_payload = create.json()

    execute = await async_client.post(
        f"/api/v1/payroll-gl-reconciliation/runs/{create_payload['run_id']}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert execute.status_code == 200
    execute_payload = execute.json()
    assert execute_payload["line_count"] >= 1

    summary = await async_client.get(
        f"/api/v1/payroll-gl-reconciliation/runs/{execute_payload['run_id']}/summary",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert summary.status_code == 200
    assert summary.json()["line_count"] >= 1

