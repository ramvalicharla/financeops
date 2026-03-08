from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.models.equity_engine import EquityRun
from financeops.db.models.users import UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.equity_engine.domain.value_objects import EquityRunTokenInput
from financeops.modules.equity_engine.infrastructure.token_builder import build_equity_run_token
from financeops.services.audit_writer import AuditEvent, AuditWriter
from tests.integration.observability_phase3_helpers import (
    seed_control_plane_for_observability,
)
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    seed_identity_user,
)


async def _seed_equity_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> uuid.UUID:
    run_token = build_equity_run_token(
        EquityRunTokenInput(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            statement_definition_version_token="stmt_v1",
            line_definition_version_token="line_v1",
            rollforward_rule_version_token="rule_v1",
            source_mapping_version_token="map_v1",
            consolidation_run_ref_nullable=None,
            fx_translation_run_ref_nullable=None,
            ownership_consolidation_run_ref_nullable=None,
            run_status="completed",
        )
    )
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=EquityRun,
        tenant_id=tenant_id,
        record_data={"run_token": run_token},
        values={
            "organisation_id": organisation_id,
            "reporting_period": reporting_period,
            "statement_definition_version_token": "stmt_v1",
            "line_definition_version_token": "line_v1",
            "rollforward_rule_version_token": "rule_v1",
            "source_mapping_version_token": "map_v1",
            "consolidation_run_ref_nullable": None,
            "fx_translation_run_ref_nullable": None,
            "ownership_consolidation_run_ref_nullable": None,
            "run_token": run_token,
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="equity_run",
            resource_name=run_token,
        ),
    )
    return row.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_observability_runs_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/observability/runs",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_observability_diff_endpoint_requires_rbac_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    user = await seed_identity_user(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        email=f"obs-rbac-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_leader,
    )
    await seed_control_plane_for_observability(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        grant_permissions=False,
    )
    await async_session.flush()
    token = create_access_token(user.id, tenant_id, user.role.value)
    response = await async_client.post(
        "/api/v1/observability/diff",
        headers={"Authorization": f"Bearer {token}"},
        json={"base_run_id": str(uuid.uuid4()), "compare_run_id": str(uuid.uuid4())},
    )
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_observability_endpoints_allow_authorized_tenant(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    user = await seed_identity_user(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        email=f"obs-ok-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_leader,
    )
    await seed_control_plane_for_observability(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        grant_permissions=True,
    )
    run_a_id = await _seed_equity_run(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
        reporting_period=date(2026, 1, 31),
    )
    run_b_id = await _seed_equity_run(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
        reporting_period=date(2026, 2, 28),
    )
    await async_session.flush()

    token = create_access_token(user.id, tenant_id, user.role.value)

    run_response = await async_client.get(
        f"/api/v1/observability/runs/{run_a_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["module_code"] == "equity_engine"

    dependency_response = await async_client.get(
        f"/api/v1/observability/runs/{run_a_id}/dependencies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dependency_response.status_code == 200
    assert dependency_response.json()["run_id"] == str(run_a_id)

    diff_response = await async_client.post(
        "/api/v1/observability/diff",
        headers={"Authorization": f"Bearer {token}"},
        json={"base_run_id": str(run_a_id), "compare_run_id": str(run_b_id)},
    )
    assert diff_response.status_code == 201
    diff_payload = diff_response.json()
    assert diff_payload["drift_flag"] is True

    replay_response = await async_client.post(
        f"/api/v1/observability/replay-validate/{run_a_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["matches"] is True

    graph_response = await async_client.get(
        f"/api/v1/observability/graph/{run_a_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert graph_response.status_code == 200
    assert graph_response.json()["root_run_id"] == str(run_a_id)

