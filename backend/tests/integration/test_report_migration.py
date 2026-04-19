from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.committed_session

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, InternalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.rls import set_tenant_context


async def _insert_definition(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    definition_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO report_definitions (
                id, tenant_id, name, description, metric_keys, filter_config,
                group_by, sort_config, export_formats, config,
                created_by, created_at, updated_at, is_active
            ) VALUES (
                :id, :tenant_id, :name, :description, CAST(:metric_keys AS jsonb), CAST(:filter_config AS jsonb),
                CAST(:group_by AS jsonb), CAST(:sort_config AS jsonb), CAST(:export_formats AS jsonb), CAST(:config AS jsonb),
                :created_by, :created_at, :updated_at, :is_active
            )
            """
        ),
        {
            "id": str(definition_id),
            "tenant_id": str(tenant_id),
            "name": "Report Definition",
            "description": "migration-test",
            "metric_keys": json.dumps(["mis.kpi.revenue"]),
            "filter_config": json.dumps({}),
            "group_by": json.dumps([]),
            "sort_config": json.dumps({}),
            "export_formats": json.dumps(["CSV"]),
            "config": json.dumps({}),
            "created_by": str(tenant_id),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "is_active": True,
        },
    )
    await session.flush()
    return definition_id


async def _insert_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    *,
    status: str = "PENDING",
) -> uuid.UUID:
    run_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO report_runs (
                id, tenant_id, definition_id, status, triggered_by, run_metadata, created_at
            ) VALUES (
                :id, :tenant_id, :definition_id, :status, :triggered_by, CAST(:run_metadata AS jsonb), :created_at
            )
            """
        ),
        {
            "id": str(run_id),
            "tenant_id": str(tenant_id),
            "definition_id": str(definition_id),
            "status": status,
            "triggered_by": str(tenant_id),
            "run_metadata": json.dumps({"origin_run_id": str(run_id)}),
            "created_at": datetime.now(UTC),
        },
    )
    await session.flush()
    return run_id


async def _insert_result(session: AsyncSession, tenant_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID:
    result_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO report_results (
                id, tenant_id, run_id, result_data, result_hash,
                export_path_csv, export_path_excel, export_path_pdf, created_at
            ) VALUES (
                :id, :tenant_id, :run_id, CAST(:result_data AS jsonb), :result_hash,
                :export_path_csv, :export_path_excel, :export_path_pdf, :created_at
            )
            """
        ),
        {
            "id": str(result_id),
            "tenant_id": str(tenant_id),
            "run_id": str(run_id),
            "result_data": json.dumps([{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}]),
            "result_hash": "a" * 64,
            "export_path_csv": "artifacts/custom_reports/r.csv",
            "export_path_excel": "artifacts/custom_reports/r.xlsx",
            "export_path_pdf": "artifacts/custom_reports/r.pdf",
            "created_at": datetime.now(UTC),
        },
    )
    await session.flush()
    return result_id


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_125_all_custom_report_tables_exist_with_expected_columns(
    async_session: AsyncSession,
) -> None:
    expected: dict[str, set[str]] = {
        "report_definitions": {
            "id",
            "tenant_id",
            "name",
            "description",
            "metric_keys",
            "filter_config",
            "group_by",
            "sort_config",
            "export_formats",
            "config",
            "created_by",
            "created_at",
            "updated_at",
            "is_active",
        },
        "report_runs": {
            "id",
            "tenant_id",
            "definition_id",
            "status",
            "triggered_by",
            "started_at",
            "completed_at",
            "error_message",
            "row_count",
            "run_metadata",
            "created_at",
        },
        "report_results": {
            "id",
            "tenant_id",
            "run_id",
            "result_data",
            "result_hash",
            "export_path_csv",
            "export_path_excel",
            "export_path_pdf",
            "created_at",
        },
    }

    for table_name, expected_columns in expected.items():
        rows = await async_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        )
        actual_columns = {str(row[0]) for row in rows.all()}
        assert expected_columns.issubset(actual_columns)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_126_append_only_blocks_update_on_report_runs(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    definition_id = await _insert_definition(async_session, tenant_id)
    run_id = await _insert_run(async_session, tenant_id, definition_id)
    await _install_append_only_guard(async_session, "report_runs")
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
        await async_session.execute(
            text("UPDATE report_runs SET status='RUNNING' WHERE id=:id"),
            {"id": run_id},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_127_append_only_blocks_delete_on_report_runs(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    definition_id = await _insert_definition(async_session, tenant_id)
    run_id = await _insert_run(async_session, tenant_id, definition_id)
    await _install_append_only_guard(async_session, "report_runs")
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
        await async_session.execute(text("DELETE FROM report_runs WHERE id=:id"), {"id": run_id})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_128_append_only_blocks_update_on_report_results(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    definition_id = await _insert_definition(async_session, tenant_id)
    run_id = await _insert_run(async_session, tenant_id, definition_id)
    result_id = await _insert_result(async_session, tenant_id, run_id)
    await _install_append_only_guard(async_session, "report_results")
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
        await async_session.execute(
            text("UPDATE report_results SET result_hash='b' WHERE id=:id"),
            {"id": result_id},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_129_rls_isolates_report_definitions_by_tenant(async_session: AsyncSession) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(text("ALTER TABLE report_definitions ENABLE ROW LEVEL SECURITY"))
    await async_session.execute(text("ALTER TABLE report_definitions FORCE ROW LEVEL SECURITY"))
    await async_session.execute(text("DROP POLICY IF EXISTS tenant_isolation ON report_definitions"))
    await async_session.execute(
        text(
            """
            CREATE POLICY tenant_isolation ON report_definitions
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )
    )

    await set_tenant_context(async_session, tenant_a)
    await _insert_definition(async_session, tenant_a)
    await async_session.commit()

    await set_tenant_context(async_session, tenant_b)
    await _insert_definition(async_session, tenant_b)
    await async_session.commit()

    await set_tenant_context(async_session, tenant_a)
    count_a = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM report_definitions
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                """
            )
        )
    ).scalar_one()

    await set_tenant_context(async_session, tenant_b)
    count_b = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM report_definitions
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                """
            )
        )
    ).scalar_one()

    assert count_a == 1
    assert count_b == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_130_report_runs_status_check_rejects_invalid_value(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    definition_id = await _insert_definition(async_session, tenant_id)

    with pytest.raises(IntegrityError):
        await _insert_run(async_session, tenant_id, definition_id, status="INVALID")
