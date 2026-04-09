from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.custom_report_builder import ReportDefinition
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
)
from financeops.modules.custom_report_builder.infrastructure.repository import (
    ReportRepository,
)
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _definition_payload() -> dict:
    return {
        "name": "API Report",
        "description": "integration",
        "metric_keys": ["mis.kpi.revenue", "mis.kpi.ebitda"],
        "filter_config": {},
        "group_by": [],
        "sort_config": {"field": "metric_key"},
        "export_formats": ["CSV", "EXCEL", "PDF"],
        "config": {},
    }


async def _create_definition(client: AsyncClient, token: str) -> dict:
    response = await client.post(
        "/api/v1/reports/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json=_definition_payload(),
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_141_create_report_definition_returns_201(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    response = await async_client.post(
        "/api/v1/reports/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=_definition_payload(),
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["id"]
    assert payload["intent_id"]
    assert payload["job_id"]
    await set_tenant_context(async_session, test_user.tenant_id)
    row = await async_session.get(ReportDefinition, uuid.UUID(payload["id"]))
    assert row is not None
    assert row.created_by_intent_id is not None
    assert row.recorded_by_job_id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_142_create_definition_with_invalid_metric_key_returns_422(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    payload = _definition_payload()
    payload["metric_keys"] = ["bad.metric.key"]
    response = await async_client.post(
        "/api/v1/reports/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_143_run_endpoint_returns_pending_and_enqueues_task(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = await _create_definition(async_client, test_access_token)
    calls: list[tuple[str, str]] = []

    def _fake_delay(run_id: str, tenant_id: str) -> None:
        calls.append((run_id, tenant_id))

    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.tasks.run_custom_report_task.delay",
        _fake_delay,
    )

    response = await async_client.post(
        "/api/v1/reports/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"definition_id": definition["id"]},
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "PENDING"
    assert data["intent_id"]
    assert data["job_id"]
    assert calls == [(data["id"], str(test_user.tenant_id))]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_144_list_runs_deduplicates_append_only_state_rows(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    repo = ReportRepository()
    await set_tenant_context(async_session, test_user.tenant_id)

    schema = ReportDefinitionSchema(
        name="Dedupe Report",
        metric_keys=["mis.kpi.revenue"],
        filter_config=FilterConfig(),
        group_by=[],
        config={},
    )
    definition = await repo.create_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=schema,
        created_by=test_user.id,
    )
    pending = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=definition.id,
        triggered_by=test_user.id,
    )
    origin = str((pending.run_metadata or {}).get("origin_run_id", pending.id))
    now = datetime.now(UTC)
    await async_session.execute(
        text(
            """
            INSERT INTO report_runs (
                id, tenant_id, definition_id, status, triggered_by,
                started_at, run_metadata, created_at
            ) VALUES (
                :id, :tenant_id, :definition_id, :status, :triggered_by,
                :started_at, CAST(:run_metadata AS jsonb), :created_at
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(test_user.tenant_id),
            "definition_id": str(definition.id),
            "status": "RUNNING",
            "triggered_by": str(test_user.id),
            "started_at": now,
            "run_metadata": json.dumps({"origin_run_id": origin, "previous_run_id": str(pending.id)}),
            "created_at": now,
        },
    )
    await async_session.execute(
        text(
            """
            INSERT INTO report_runs (
                id, tenant_id, definition_id, status, triggered_by,
                started_at, completed_at, row_count, run_metadata, created_at
            ) VALUES (
                :id, :tenant_id, :definition_id, :status, :triggered_by,
                :started_at, :completed_at, :row_count, CAST(:run_metadata AS jsonb), :created_at
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(test_user.tenant_id),
            "definition_id": str(definition.id),
            "status": "COMPLETE",
            "triggered_by": str(test_user.id),
            "started_at": now + timedelta(seconds=1),
            "completed_at": now + timedelta(seconds=1),
            "row_count": 1,
            "run_metadata": json.dumps({"origin_run_id": origin, "previous_run_id": str(pending.id)}),
            "created_at": now + timedelta(seconds=1),
        },
    )
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/reports/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["status"] == "COMPLETE"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_145_get_run_result_returns_result_data(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    repo = ReportRepository()
    await set_tenant_context(async_session, test_user.tenant_id)
    definition = await repo.create_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=ReportDefinitionSchema(
            name="Result Report",
            metric_keys=["mis.kpi.revenue"],
            filter_config=FilterConfig(),
            group_by=[],
            config={},
        ),
        created_by=test_user.id,
    )
    run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=definition.id,
        triggered_by=test_user.id,
    )
    await repo.save_result(
        db=async_session,
        tenant_id=test_user.tenant_id,
        run_id=run.id,
        result_data=[{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}],
        result_hash="a" * 64,
        export_paths={},
    )
    await Phase4ControlPlaneService(async_session).ensure_snapshot_for_subject(
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        actor_role=test_user.role.value,
        subject_type="report_run",
        subject_id=str(run.id),
        trigger_event="report_generation_complete",
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/reports/runs/{run.id}/result",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["result_data"]
    assert payload["snapshot_refs"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_145b_update_definition_uses_governed_pipeline(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    definition = await _create_definition(async_client, test_access_token)

    response = await async_client.patch(
        f"/api/v1/reports/definitions/{definition['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"description": "updated via intent"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["intent_id"]
    assert payload["job_id"]
    assert payload["description"] == "updated via intent"
    await set_tenant_context(async_session, test_user.tenant_id)
    row = await async_session.get(ReportDefinition, uuid.UUID(definition["id"]))
    assert row is not None
    assert row.recorded_by_job_id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_146_download_csv_returns_file_response(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = ReportRepository()
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.api.routes.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    await set_tenant_context(async_session, test_user.tenant_id)
    definition = await repo.create_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=ReportDefinitionSchema(
            name="Download Report",
            metric_keys=["mis.kpi.revenue"],
            filter_config=FilterConfig(),
            group_by=[],
            config={},
        ),
        created_by=test_user.id,
    )
    run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=definition.id,
        triggered_by=test_user.id,
    )
    storage_path = f"artifacts/custom_reports/{test_user.tenant_id}/{run.id}/download.csv"
    file_path = tmp_path / storage_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"metric_key,metric_value\nmis.kpi.revenue,100.00\n")
    await repo.save_result(
        db=async_session,
        tenant_id=test_user.tenant_id,
        run_id=run.id,
        result_data=[{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}],
        result_hash="b" * 64,
        export_paths={"CSV": storage_path},
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/reports/runs/{run.id}/download/csv",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_147_delete_definition_soft_deletes_and_returns_204(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    definition = await _create_definition(async_client, test_access_token)
    response = await async_client.delete(
        f"/api/v1/reports/definitions/{definition['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 204

    await set_tenant_context(async_session, test_user.tenant_id)
    row = (
        await async_session.execute(
            text("SELECT is_active FROM report_definitions WHERE id = CAST(:id AS uuid)"),
            {"id": definition["id"]},
        )
    ).scalar_one()
    assert row is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_148_rls_hides_tenant_b_definitions_from_tenant_a(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _create_definition(async_client, test_access_token)

    tenant_b_id = uuid.uuid4()
    tenant_b_user_id = uuid.uuid4()
    tenant_b = IamTenant(
        id=tenant_b_id,
        tenant_id=tenant_b_id,
        display_name="Tenant B",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Tenant B",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    tenant_b_user = IamUser(
        id=tenant_b_user_id,
        tenant_id=tenant_b_id,
        email=f"tenantb_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Tenant B User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(tenant_b)
    async_session.add(tenant_b_user)
    await async_session.flush()

    repo = ReportRepository()
    await set_tenant_context(async_session, tenant_b_id)
    await repo.create_definition(
        db=async_session,
        tenant_id=tenant_b_id,
        schema=ReportDefinitionSchema(
            name="Tenant B Report",
            metric_keys=["mis.kpi.revenue"],
            filter_config=FilterConfig(),
            group_by=[],
            config={},
        ),
        created_by=tenant_b_user_id,
    )
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/reports/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["data"]]
    assert "Tenant B Report" not in names
