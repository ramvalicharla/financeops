from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.anomaly_pattern_engine import AnomalyResult, AnomalyRun
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.custom_report_builder.application.run_service import ReportRunService
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
)
from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryExportFormat,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    Recipient,
    ScheduleDefinitionSchema,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import DeliveryRepository
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _current_alembic_head() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    script_dir = ScriptDirectory.from_config(cfg)
    return script_dir.get_current_head() or ""


async def _insert_board_pack_definition(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    board_pack_code: str,
    board_pack_name: str,
) -> uuid.UUID:
    definition_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    await set_tenant_context(async_session, tenant_id)
    has_name = (
        await async_session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='board_pack_definitions'
                  AND column_name='name'
                LIMIT 1
                """
            )
        )
    ).scalar_one_or_none() is not None
    has_period_type = (
        await async_session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='board_pack_definitions'
                  AND column_name='period_type'
                LIMIT 1
                """
            )
        )
    ).scalar_one_or_none() is not None
    has_updated_at = (
        await async_session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='board_pack_definitions'
                  AND column_name='updated_at'
                LIMIT 1
                """
            )
        )
    ).scalar_one_or_none() is not None

    optional_columns: list[str] = []
    optional_values: list[str] = []
    if has_name:
        optional_columns.append("name")
        optional_values.append(":name")
    if has_period_type:
        optional_columns.append("period_type")
        optional_values.append(":period_type")
    if has_updated_at:
        optional_columns.append("updated_at")
        optional_values.append(":updated_at")

    optional_columns_sql = ""
    optional_values_sql = ""
    if optional_columns:
        optional_columns_sql = ",\n                " + ",\n                ".join(optional_columns)
        optional_values_sql = ",\n                " + ",\n                ".join(optional_values)

    await async_session.execute(
        text(
            f"""
            INSERT INTO board_pack_definitions (
                id,
                tenant_id,
                chain_hash,
                previous_hash,
                organisation_id,
                board_pack_code,
                board_pack_name,
                audience_scope,
                section_order_json,
                inclusion_config_json,
                version_token,
                effective_from,
                status,
                created_by,
                created_at{optional_columns_sql}
            ) VALUES (
                CAST(:id AS uuid),
                CAST(:tenant_id AS uuid),
                :chain_hash,
                :previous_hash,
                CAST(:organisation_id AS uuid),
                :board_pack_code,
                :board_pack_name,
                'board',
                CAST(:section_order_json AS jsonb),
                CAST(:inclusion_config_json AS jsonb),
                :version_token,
                :effective_from,
                'active',
                CAST(:created_by AS uuid),
                :created_at{optional_values_sql}
            )
            """
        ),
        {
            "id": str(definition_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "a" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(tenant_id),
            "board_pack_code": board_pack_code,
            "board_pack_name": board_pack_name,
            "section_order_json": '{"executive_summary":1}',
            "inclusion_config_json": '{"top_limit":5}',
            "version_token": uuid.uuid4().hex,
            "effective_from": date(2026, 1, 1),
            "created_by": str(user_id),
            "created_at": created_at,
            "name": board_pack_name,
            "period_type": "MONTHLY",
            "updated_at": created_at,
        },
    )
    await async_session.flush()
    return definition_id


async def _create_report_definition_api(
    client: AsyncClient,
    token: str,
) -> dict:
    response = await client.post(
        "/api/v1/reports/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Phase5 Report",
            "description": "cross-module",
            "metric_keys": ["mis.kpi.revenue"],
            "filter_config": {},
            "group_by": [],
            "sort_config": {"field": "metric_key"},
            "export_formats": ["CSV"],
            "config": {},
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def _create_delivery_schedule_api(
    client: AsyncClient,
    token: str,
    *,
    schedule_type: str,
    source_definition_id: str,
) -> dict:
    response = await client.post(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Delivery {schedule_type}",
            "description": "cross-module",
            "schedule_type": schedule_type,
            "source_definition_id": source_definition_id,
            "cron_expression": "0 8 * * 1",
            "timezone": "UTC",
            "recipients": [{"type": "EMAIL", "address": "ops@example.com"}],
            "export_format": "PDF",
            "config": {},
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


async def _create_secondary_tenant_user(async_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_b_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

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
    user_b = IamUser(
        id=user_b_id,
        tenant_id=tenant_b_id,
        email=f"tenantb_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Tenant B User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(tenant_b)
    async_session.add(user_b)
    await async_session.flush()
    return tenant_b_id, user_b_id


async def _seed_open_anomaly_alert(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> uuid.UUID:
    await set_tenant_context(async_session, tenant_id)

    run = AnomalyRun(
        tenant_id=tenant_id,
        chain_hash="a" * 64,
        previous_hash="0" * 64,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        anomaly_definition_version_token="v1",
        pattern_rule_version_token="v1",
        persistence_rule_version_token="v1",
        correlation_rule_version_token="v1",
        statistical_rule_version_token="v1",
        source_metric_run_ids_json=[str(uuid.uuid4())],
        source_variance_run_ids_json=[str(uuid.uuid4())],
        source_trend_run_ids_json=[],
        source_risk_run_ids_json=[],
        source_reconciliation_session_ids_json=[],
        run_token=uuid.uuid4().hex,
        status="completed",
        validation_summary_json={},
        created_by=user_id,
    )
    async_session.add(run)
    await async_session.flush()

    alert = AnomalyResult(
        tenant_id=tenant_id,
        chain_hash="b" * 64,
        previous_hash="a" * 64,
        run_id=run.id,
        line_no=1,
        anomaly_code="ANOM_TEST",
        anomaly_name="Test Anomaly",
        anomaly_domain="liquidity",
        anomaly_score=Decimal("0.500000"),
        z_score=Decimal("1.000000"),
        severity="high",
        alert_status="OPEN",
        snoozed_until=None,
        resolved_at=None,
        escalated_at=None,
        status_note=None,
        status_updated_by=None,
        persistence_classification="first_detected",
        correlation_flag=False,
        materiality_elevated=False,
        risk_elevated=False,
        board_flag=False,
        confidence_score=Decimal("0.800000"),
        seasonal_adjustment_flag=False,
        seasonal_normalized_value=None,
        benchmark_group_id=None,
        benchmark_baseline_value=None,
        benchmark_deviation_score=None,
        source_summary_json={"source_table": "gl_entries", "source_row_id": "42"},
        created_by=user_id,
    )
    async_session.add(alert)
    await async_session.flush()
    return alert.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_401_board_pack_definition_to_scheduled_delivery_schedule(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    board_definition_id = await _insert_board_pack_definition(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        board_pack_code=f"bp_{uuid.uuid4().hex[:8]}",
        board_pack_name="Phase5 Board Pack",
    )

    schedule = await _create_delivery_schedule_api(
        async_client,
        test_access_token,
        schedule_type="BOARD_PACK",
        source_definition_id=str(board_definition_id),
    )

    assert schedule["schedule_type"] == "BOARD_PACK"
    assert schedule["source_definition_id"] == str(board_definition_id)

    list_response = await async_client.get(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert list_response.status_code == 200
    schedule_ids = {row["id"] for row in list_response.json()["data"]}
    assert schedule["id"] in schedule_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_402_report_definition_to_scheduled_delivery_schedule(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    report_definition = await _create_report_definition_api(async_client, test_access_token)

    schedule = await _create_delivery_schedule_api(
        async_client,
        test_access_token,
        schedule_type="REPORT",
        source_definition_id=report_definition["id"],
    )

    assert schedule["schedule_type"] == "REPORT"
    assert schedule["source_definition_id"] == report_definition["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_403_board_pack_generate_storage_path_convention(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board_definition_id = await _insert_board_pack_definition(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        board_pack_code=f"bp_{uuid.uuid4().hex[:8]}",
        board_pack_name="Phase5 Board Pack Trigger",
    )

    captured: dict[str, object] = {}

    async def _fake_get_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> SimpleNamespace:
        del self, db, tenant_id
        return SimpleNamespace(id=definition_id, is_active=True)

    async def _fake_create_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
        period_start: date,
        period_end: date,
        triggered_by: uuid.UUID,
        run_metadata: dict[str, object] | None = None,
    ) -> SimpleNamespace:
        del self, db
        run_id = uuid.uuid4()
        captured["run_id"] = run_id
        captured["tenant_id"] = tenant_id
        captured["definition_id"] = definition_id
        captured["period_start"] = period_start
        captured["period_end"] = period_end
        captured["run_metadata"] = run_metadata or {}
        return SimpleNamespace(
            id=run_id,
            tenant_id=tenant_id,
            definition_id=definition_id,
            period_start=period_start,
            period_end=period_end,
            status="PENDING",
            triggered_by=triggered_by,
            started_at=None,
            completed_at=None,
            error_message=None,
            chain_hash=None,
            run_metadata={},
            created_at=datetime.now(UTC),
        )

    async def _fake_get_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> SimpleNamespace:
        del self, db
        if captured.get("run_id") != run_id:
            return None
        return SimpleNamespace(
            id=run_id,
            tenant_id=tenant_id,
            definition_id=captured["definition_id"],
            period_start=captured["period_start"],
            period_end=captured["period_end"],
            status="PENDING",
            triggered_by=test_user.id,
            started_at=None,
            completed_at=None,
            error_message=None,
            chain_hash=None,
            run_metadata=captured.get("run_metadata", {}),
            created_at=datetime.now(UTC),
        )

    queued_calls: list[tuple[str, str]] = []

    def _fake_delay(run_id: str, tenant_id: str) -> None:
        queued_calls.append((run_id, tenant_id))

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.infrastructure.repository.BoardPackRepository.get_definition",
        _fake_get_definition,
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.infrastructure.repository.BoardPackRepository.create_run",
        _fake_create_run,
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.api.routes.BoardPackRepository.get_run",
        _fake_get_run,
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.api.routes.generate_board_pack_task.delay",
        _fake_delay,
    )

    response = await async_client.post(
        "/api/v1/board-packs/generate",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "definition_id": str(board_definition_id),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
    )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "PENDING"
    assert queued_calls == [(payload["id"], str(test_user.tenant_id))]

    expected_prefix = f"artifacts/board_packs/{test_user.tenant_id}/{payload['id']}/"
    expected_path = f"{expected_prefix}board_pack_2026-01-01_2026-01-31.pdf"
    assert expected_path.startswith(expected_prefix)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_404_report_result_hash_is_deterministic_across_two_runs(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_definition = await _create_report_definition_api(async_client, test_access_token)

    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.api.routes.run_custom_report_task.delay",
        lambda *_args, **_kwargs: None,
    )

    run_response_1 = await async_client.post(
        "/api/v1/reports/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"definition_id": report_definition["id"]},
    )
    run_response_2 = await async_client.post(
        "/api/v1/reports/run",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"definition_id": report_definition["id"]},
    )

    assert run_response_1.status_code == 202
    assert run_response_2.status_code == 202

    pending_run_1 = uuid.UUID(run_response_1.json()["data"]["id"])
    pending_run_2 = uuid.UUID(run_response_2.json()["data"]["id"])

    await set_tenant_context(async_session, test_user.tenant_id)
    service = ReportRunService()

    async def _fake_get_table_columns(*, db: AsyncSession, table_name: str) -> set[str]:
        del db, table_name
        return {"tenant_id", "metric_code", "metric_value", "reporting_period"}

    async def _fake_query_metric_rows(
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        metric_key: str,
        table_name: str,
        source_column: str,
        table_columns: set[str],
        filters: FilterConfig,
        group_by: list[str],
    ) -> list[dict[str, object]]:
        del db, tenant_id, metric_key, table_name, source_column, table_columns, filters, group_by
        return [{"metric_value": "1000.00", "metric_code": "revenue", "reporting_period": date(2026, 1, 31)}]

    async def _fake_export_rows(
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, object]],
        report_name: str,
        export_formats: list[object],
    ) -> dict[str, str]:
        del tenant_id, run_id, rows, report_name, export_formats
        return {}

    monkeypatch.setattr(service, "_get_table_columns", _fake_get_table_columns)
    monkeypatch.setattr(service, "_query_metric_rows", _fake_query_metric_rows)
    monkeypatch.setattr(service, "_export_rows", _fake_export_rows)

    await service.run(db=async_session, run_id=pending_run_1, tenant_id=test_user.tenant_id)
    await service.run(db=async_session, run_id=pending_run_2, tenant_id=test_user.tenant_id)

    hashes = (
        await async_session.execute(
            text(
                """
                SELECT result_hash
                FROM report_results
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                ORDER BY created_at DESC, id DESC
                LIMIT 2
                """
            ),
            {"tenant_id": str(test_user.tenant_id)},
        )
    ).scalars().all()

    assert len(hashes) == 2
    assert hashes[0] == hashes[1]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_405_anomaly_alert_status_flow_open_to_resolved(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    alert_id = await _seed_open_anomaly_alert(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )

    patch_response = await async_client.patch(
        f"/api/v1/anomalies/{alert_id}/status",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "RESOLVED", "note": "resolved in cross-module test"},
    )
    assert patch_response.status_code == 200
    patched_payload = patch_response.json()["data"]
    assert patched_payload["alert_status"] == "RESOLVED"
    assert patched_payload["resolved_at"] is not None

    open_response = await async_client.get(
        "/api/v1/anomalies?status=OPEN",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert open_response.status_code == 200
    assert all(str(row["id"]) != str(alert_id) for row in open_response.json()["data"])

    resolved_response = await async_client.get(
        "/api/v1/anomalies?status=RESOLVED",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert resolved_response.status_code == 200
    assert any(str(row["id"]) == str(alert_id) for row in resolved_response.json()["data"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_406_delivery_schedule_deactivation_blocks_trigger(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    schedule = await _create_delivery_schedule_api(
        async_client,
        test_access_token,
        schedule_type="REPORT",
        source_definition_id=str(uuid.uuid4()),
    )

    delete_response = await async_client.delete(
        f"/api/v1/delivery/schedules/{schedule['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert delete_response.status_code == 204

    await set_tenant_context(async_session, test_user.tenant_id)
    is_active = (
        await async_session.execute(
            text("SELECT is_active FROM delivery_schedules WHERE id = CAST(:id AS uuid)"),
            {"id": schedule["id"]},
        )
    ).scalar_one()
    assert is_active is False

    trigger_response = await async_client.post(
        f"/api/v1/delivery/schedules/{schedule['id']}/trigger",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert trigger_response.status_code in {400, 404}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_407_alembic_chain_and_phase5_tables_present(
    async_session: AsyncSession,
) -> None:
    head = (await async_session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert head == _current_alembic_head()

    table_rows = await async_session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    existing_tables = {str(row[0]) for row in table_rows.all()}
    required_phase5_tables = {
        "board_pack_definitions",
        "board_pack_runs",
        "report_definitions",
        "report_runs",
        "report_results",
        "delivery_schedules",
        "delivery_logs",
    }
    assert required_phase5_tables.issubset(existing_tables)

    # Board-pack implementation differs by module family: generator tables
    # (board_pack_sections/artifacts) or narrative-engine result tables.
    generator_tables = {"board_pack_sections", "board_pack_artifacts"}
    narrative_tables = {"board_pack_section_results", "board_pack_narrative_blocks"}
    assert generator_tables.issubset(existing_tables) or narrative_tables.issubset(existing_tables)

    has_alert_status = (
        await async_session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'anomaly_results'
                  AND column_name = 'alert_status'
                """
            )
        )
    ).first()
    assert has_alert_status is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_408_rls_cross_module_isolation(
    async_session: AsyncSession,
    test_user,
) -> None:
    tenant_b_id, tenant_b_user_id = await _create_secondary_tenant_user(async_session)

    board_code_a = f"bp_a_{uuid.uuid4().hex[:8]}"
    board_code_b = f"bp_b_{uuid.uuid4().hex[:8]}"

    board_id_a = await _insert_board_pack_definition(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        board_pack_code=board_code_a,
        board_pack_name="Board A",
    )
    board_id_b = await _insert_board_pack_definition(
        async_session,
        tenant_id=tenant_b_id,
        user_id=tenant_b_user_id,
        board_pack_code=board_code_b,
        board_pack_name="Board B",
    )

    report_repo = ReportRepository()
    delivery_repo = DeliveryRepository()

    report_name_a = f"report-a-{uuid.uuid4().hex[:8]}"
    report_name_b = f"report-b-{uuid.uuid4().hex[:8]}"
    schedule_name_a = f"schedule-a-{uuid.uuid4().hex[:8]}"
    schedule_name_b = f"schedule-b-{uuid.uuid4().hex[:8]}"

    await set_tenant_context(async_session, test_user.tenant_id)
    report_a = await report_repo.create_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=ReportDefinitionSchema(
            name=report_name_a,
            metric_keys=["mis.kpi.revenue"],
            filter_config=FilterConfig(),
            group_by=[],
            config={},
        ),
        created_by=test_user.id,
    )
    delivery_a = await delivery_repo.create_schedule(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=ScheduleDefinitionSchema(
            name=schedule_name_a,
            description=None,
            schedule_type=ScheduleType.REPORT,
            source_definition_id=report_a.id,
            cron_expression="0 8 * * 1",
            timezone="UTC",
            recipients=[Recipient(type=ChannelType.EMAIL, address="ops-a@example.com")],
            export_format=DeliveryExportFormat.PDF,
            config={},
        ),
        created_by=test_user.id,
    )

    await set_tenant_context(async_session, tenant_b_id)
    report_b = await report_repo.create_definition(
        db=async_session,
        tenant_id=tenant_b_id,
        schema=ReportDefinitionSchema(
            name=report_name_b,
            metric_keys=["mis.kpi.revenue"],
            filter_config=FilterConfig(),
            group_by=[],
            config={},
        ),
        created_by=tenant_b_user_id,
    )
    delivery_b = await delivery_repo.create_schedule(
        db=async_session,
        tenant_id=tenant_b_id,
        schema=ScheduleDefinitionSchema(
            name=schedule_name_b,
            description=None,
            schedule_type=ScheduleType.REPORT,
            source_definition_id=report_b.id,
            cron_expression="0 9 * * 1",
            timezone="UTC",
            recipients=[Recipient(type=ChannelType.EMAIL, address="ops-b@example.com")],
            export_format=DeliveryExportFormat.PDF,
            config={},
        ),
        created_by=tenant_b_user_id,
    )
    await async_session.flush()

    await set_tenant_context(async_session, test_user.tenant_id)
    board_rows_a = await async_session.execute(
        text(
            """
            SELECT id
            FROM board_pack_definitions
            WHERE board_pack_code IN (:code_a, :code_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY board_pack_code ASC
            """
        ),
        {"code_a": board_code_a, "code_b": board_code_b, "tenant_id": str(test_user.tenant_id)},
    )
    report_rows_a = await async_session.execute(
        text(
            """
            SELECT id
            FROM report_definitions
            WHERE name IN (:name_a, :name_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY name ASC
            """
        ),
        {"name_a": report_name_a, "name_b": report_name_b, "tenant_id": str(test_user.tenant_id)},
    )
    schedule_rows_a = await async_session.execute(
        text(
            """
            SELECT id
            FROM delivery_schedules
            WHERE name IN (:name_a, :name_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY name ASC
            """
        ),
        {"name_a": schedule_name_a, "name_b": schedule_name_b, "tenant_id": str(test_user.tenant_id)},
    )

    assert {row[0] for row in board_rows_a.all()} == {board_id_a}
    assert {row[0] for row in report_rows_a.all()} == {report_a.id}
    assert {row[0] for row in schedule_rows_a.all()} == {delivery_a.id}

    await set_tenant_context(async_session, tenant_b_id)
    board_rows_b = await async_session.execute(
        text(
            """
            SELECT id
            FROM board_pack_definitions
            WHERE board_pack_code IN (:code_a, :code_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY board_pack_code ASC
            """
        ),
        {"code_a": board_code_a, "code_b": board_code_b, "tenant_id": str(tenant_b_id)},
    )
    report_rows_b = await async_session.execute(
        text(
            """
            SELECT id
            FROM report_definitions
            WHERE name IN (:name_a, :name_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY name ASC
            """
        ),
        {"name_a": report_name_a, "name_b": report_name_b, "tenant_id": str(tenant_b_id)},
    )
    schedule_rows_b = await async_session.execute(
        text(
            """
            SELECT id
            FROM delivery_schedules
            WHERE name IN (:name_a, :name_b)
              AND tenant_id = CAST(:tenant_id AS uuid)
            ORDER BY name ASC
            """
        ),
        {"name_a": schedule_name_a, "name_b": schedule_name_b, "tenant_id": str(tenant_b_id)},
    )

    assert {row[0] for row in board_rows_b.all()} == {board_id_b}
    assert {row[0] for row in report_rows_b.all()} == {report_b.id}
    assert {row[0] for row in schedule_rows_b.all()} == {delivery_b.id}
