from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.reconciliation_phase1f2_helpers import (
    build_reconciliation_service,
    ensure_tenant_context,
    seed_control_plane_for_reconciliation_bridge,
    seed_gl_tb_pair,
    seed_identity_user,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_sessions_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/reconciliation/sessions",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": "00000000-0000-0000-0000-000000000010",
            "reconciliation_type": "gl_vs_trial_balance",
            "source_a_type": "gl_entries",
            "source_a_ref": "a",
            "source_b_type": "trial_balance_rows",
            "source_b_ref": "b",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "materiality_config_json": {"absolute_threshold": "0"},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_sessions_endpoint_requires_module_enablement(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_reconciliation_bridge(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/reconciliation/sessions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reconciliation_type": "gl_vs_trial_balance",
            "source_a_type": "gl_entries",
            "source_a_ref": "a",
            "source_b_type": "trial_balance_rows",
            "source_b_ref": "b",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "materiality_config_json": {"absolute_threshold": "0"},
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_sessions_endpoint_requires_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_reconciliation_bridge(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/reconciliation/sessions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reconciliation_type": "gl_vs_trial_balance",
            "source_a_type": "gl_entries",
            "source_a_ref": "a",
            "source_b_type": "trial_balance_rows",
            "source_b_ref": "b",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "materiality_config_json": {"absolute_threshold": "0"},
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_create_and_run_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_reconciliation_bridge(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, test_user.tenant_id)
    await seed_gl_tb_pair(
        async_session, tenant_id=test_user.tenant_id, created_by=test_user.id
    )

    created = await async_client.post(
        "/api/v1/reconciliation/sessions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reconciliation_type": "gl_vs_trial_balance",
            "source_a_type": "gl_entries",
            "source_a_ref": "gl_seed",
            "source_b_type": "trial_balance_rows",
            "source_b_ref": "tb_seed",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "materiality_config_json": {"absolute_threshold": "0"},
        },
    )
    assert created.status_code == 201
    session_id = created.json()["data"]["session_id"]

    run = await async_client.post(
        f"/api/v1/reconciliation/sessions/{session_id}/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert run.status_code == 200
    payload = run.json()["data"]
    assert payload["line_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_lines_endpoint_is_tenant_scoped(
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
        email="recon_b@example.com",
    )
    await seed_control_plane_for_reconciliation_bridge(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    await seed_gl_tb_pair(async_session, tenant_id=tenant_b, created_by=user_b)
    service = build_reconciliation_service(async_session)
    created = await service.create_session(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        reconciliation_type="gl_vs_trial_balance",
        source_a_type="gl_entries",
        source_a_ref="gl_seed_b",
        source_b_type="trial_balance_rows",
        source_b_ref="tb_seed_b",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        matching_rule_version="recon_match_v1",
        tolerance_rule_version="recon_tolerance_v1",
        materiality_config_json={"absolute_threshold": "0"},
        created_by=user_b,
    )
    await service.run_session(
        tenant_id=tenant_b,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=user_b,
    )

    await seed_control_plane_for_reconciliation_bridge(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.get(
        f"/api/v1/reconciliation/sessions/{created['session_id']}/lines",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.json()["data"] == []

