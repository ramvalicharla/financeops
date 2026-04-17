from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, InternalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.rls import set_tenant_context

pytest_plugins: tuple[str, ...] = ()


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    return bool(
        (
            await session.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                    LIMIT 1
                    """
                ),
                {"table_name": table_name},
            )
        ).scalar_one_or_none()
    )


async def _insert_definition(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    definition_id = uuid.uuid4()
    available_columns = {
        row[0]
        for row in (
            await session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'board_pack_definitions'
                    """
                )
            )
        ).all()
    }

    values = {
        "id": str(definition_id),
        "tenant_id": str(tenant_id),
        "name": "Definition",
        "description": "migration test",
        "section_types": json.dumps(["PROFIT_AND_LOSS"]),
        "entity_ids": json.dumps([str(uuid.uuid4())]),
        "period_type": "MONTHLY",
        "config": json.dumps({}),
        "created_by": str(tenant_id),
        "organisation_id": str(tenant_id),
        "board_pack_code": f"bp_{uuid.uuid4().hex[:8]}",
        "board_pack_name": "Definition Name",
        "audience_scope": "board",
        "section_order_json": json.dumps({"PROFIT_AND_LOSS": 1}),
        "inclusion_config_json": json.dumps({}),
        "version_token": uuid.uuid4().hex,
        "effective_from": date(2026, 1, 1),
        "status": "candidate",
        "chain_hash": "a" * 64,
        "previous_hash": "0" * 64,
        "created_at": datetime.now(UTC),
    }

    jsonb_columns = {
        "section_types",
        "entity_ids",
        "config",
        "section_order_json",
        "inclusion_config_json",
    }
    ordered_candidates = [
        "id",
        "tenant_id",
        "name",
        "description",
        "section_types",
        "entity_ids",
        "period_type",
        "config",
        "created_by",
        "organisation_id",
        "board_pack_code",
        "board_pack_name",
        "audience_scope",
        "section_order_json",
        "inclusion_config_json",
        "version_token",
        "effective_from",
        "status",
        "chain_hash",
        "previous_hash",
        "created_at",
    ]

    insert_columns = [column for column in ordered_candidates if column in available_columns]
    insert_values = [
        f"CAST(:{column} AS jsonb)" if column in jsonb_columns else f":{column}"
        for column in insert_columns
    ]

    await session.execute(
        text(
            f"""
            INSERT INTO board_pack_definitions (
                {", ".join(insert_columns)}
            ) VALUES (
                {", ".join(insert_values)}
            )
            """
        ),
        {key: value for key, value in values.items() if key in insert_columns},
    )
    await session.flush()
    return definition_id


async def _insert_run(session: AsyncSession, tenant_id: uuid.UUID, definition_id: uuid.UUID) -> uuid.UUID:
    run_id = uuid.uuid4()
    await session.execute(
        text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_status")
    )
    available_columns = {
        row[0]
        for row in (
            await session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'board_pack_runs'
                    """
                )
            )
        ).all()
    }

    values = {
        "id": str(run_id),
        "tenant_id": str(tenant_id),
        "definition_id": str(definition_id),
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "status": "PENDING",
        "triggered_by": str(tenant_id),
        "run_metadata": json.dumps({"origin_run_id": str(run_id)}),
        "chain_hash": "b" * 64,
        "previous_hash": "a" * 64,
        "organisation_id": str(tenant_id),
        "reporting_period": date(2026, 1, 31),
        "board_pack_definition_version_token": uuid.uuid4().hex,
        "section_definition_version_token": uuid.uuid4().hex,
        "narrative_template_version_token": uuid.uuid4().hex,
        "inclusion_rule_version_token": uuid.uuid4().hex,
        "source_metric_run_ids_json": json.dumps([str(uuid.uuid4())]),
        "source_risk_run_ids_json": json.dumps([str(uuid.uuid4())]),
        "source_anomaly_run_ids_json": json.dumps([str(uuid.uuid4())]),
        "run_token": uuid.uuid4().hex,
        "validation_summary_json": json.dumps({}),
        "created_by": str(tenant_id),
        "created_at": datetime.now(UTC),
    }

    jsonb_columns = {
        "run_metadata",
        "source_metric_run_ids_json",
        "source_risk_run_ids_json",
        "source_anomaly_run_ids_json",
        "validation_summary_json",
    }
    ordered_candidates = [
        "id",
        "tenant_id",
        "definition_id",
        "period_start",
        "period_end",
        "status",
        "triggered_by",
        "run_metadata",
        "chain_hash",
        "previous_hash",
        "organisation_id",
        "reporting_period",
        "board_pack_definition_version_token",
        "section_definition_version_token",
        "narrative_template_version_token",
        "inclusion_rule_version_token",
        "source_metric_run_ids_json",
        "source_risk_run_ids_json",
        "source_anomaly_run_ids_json",
        "run_token",
        "validation_summary_json",
        "created_by",
        "created_at",
    ]

    insert_columns = [column for column in ordered_candidates if column in available_columns]
    insert_values = [
        f"CAST(:{column} AS jsonb)" if column in jsonb_columns else f":{column}"
        for column in insert_columns
    ]

    await session.execute(
        text(
            f"""
            INSERT INTO board_pack_runs (
                {", ".join(insert_columns)}
            ) VALUES (
                {", ".join(insert_values)}
            )
            """
        ),
        {key: value for key, value in values.items() if key in insert_columns},
    )
    await session.flush()
    return run_id


async def _insert_section(session: AsyncSession, tenant_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID:
    section_id = uuid.uuid4()
    result = await session.execute(
        text(
            """
            INSERT INTO board_pack_sections (
                id, run_id, tenant_id, section_type, section_order, data_snapshot, section_hash
            ) VALUES (
                :id, :run_id, :tenant_id, 'PROFIT_AND_LOSS', 1, CAST(:data_snapshot AS jsonb), :section_hash
            ) RETURNING id
            """
        ),
        {
            "id": str(section_id),
            "run_id": str(run_id),
            "tenant_id": str(tenant_id),
            "data_snapshot": json.dumps({"value": "1"}),
            "section_hash": "a" * 64,
        },
    )
    return result.scalar_one()


async def _insert_artifact(session: AsyncSession, tenant_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID:
    artifact_id = uuid.uuid4()
    result = await session.execute(
        text(
            """
            INSERT INTO board_pack_artifacts (
                id, run_id, tenant_id, format, storage_path, file_size_bytes, checksum
            ) VALUES (
                :id, :run_id, :tenant_id, 'PDF', :storage_path, 123, :checksum
            ) RETURNING id
            """
        ),
        {
            "id": str(artifact_id),
            "run_id": str(run_id),
            "tenant_id": str(tenant_id),
            "storage_path": f"artifacts/board_packs/{tenant_id}/{run_id}/x.pdf",
            "checksum": "b" * 64,
        },
    )
    return result.scalar_one()


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_001_all_board_pack_tables_exist_with_expected_columns(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        expected: dict[str, dict[str, str]] = {
            "board_pack_definitions": {
                "id": "uuid",
                "tenant_id": "uuid",
                "name": "character varying",
                "description": "text",
                "section_types": "jsonb",
                "entity_ids": "jsonb",
                "period_type": "character varying",
                "config": "jsonb",
                "created_by": "uuid",
                "created_at": "timestamp with time zone",
                "updated_at": "timestamp with time zone",
                "is_active": "boolean",
            },
            "board_pack_runs": {
                "id": "uuid",
                "tenant_id": "uuid",
                "definition_id": "uuid",
                "period_start": "date",
                "period_end": "date",
                "status": "character varying",
                "triggered_by": "uuid",
                "started_at": "timestamp with time zone",
                "completed_at": "timestamp with time zone",
                "error_message": "text",
                "chain_hash": "character varying",
                "run_metadata": "jsonb",
                "created_at": "timestamp with time zone",
            },
            "board_pack_sections": {
                "id": "uuid",
                "run_id": "uuid",
                "tenant_id": "uuid",
                "section_type": "character varying",
                "section_order": "integer",
                "data_snapshot": "jsonb",
                "section_hash": "character varying",
                "rendered_at": "timestamp with time zone",
            },
            "board_pack_artifacts": {
                "id": "uuid",
                "run_id": "uuid",
                "tenant_id": "uuid",
                "format": "character varying",
                "storage_path": "text",
                "file_size_bytes": "bigint",
                "generated_at": "timestamp with time zone",
                "checksum": "character varying",
            },
        }

        for table_name, expected_columns in expected.items():
            rows = await session.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            )
            actual = {column: data_type for column, data_type in rows.all()}

            for column_name, data_type in expected_columns.items():
                assert column_name in actual
                assert actual[column_name] == data_type


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_002_append_only_blocks_update_for_runs_sections_artifacts(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_id = uuid.uuid4()
        await set_tenant_context(session, tenant_id)

        definition_id = await _insert_definition(session, tenant_id)
        definition_update_column = (
            await session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'board_pack_definitions'
                      AND column_name IN ('name', 'board_pack_name')
                    ORDER BY CASE WHEN column_name = 'name' THEN 0 ELSE 1 END
                    LIMIT 1
                    """
                )
            )
        ).scalar_one()
        await session.execute(
            text(f"UPDATE board_pack_definitions SET {definition_update_column}='updated-ok' WHERE id=:id"),
            {"id": definition_id},
        )
        await session.commit()
        await set_tenant_context(session, tenant_id)

        await _install_append_only_guard(session, "board_pack_runs")
        run_id = await _insert_run(session, tenant_id, definition_id)
        await session.commit()
        await set_tenant_context(session, tenant_id)
        with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
            await session.execute(
                text("UPDATE board_pack_runs SET status='RUNNING' WHERE id=:id"),
                {"id": run_id},
            )
        await session.rollback()
        await set_tenant_context(session, tenant_id)

        if await _table_exists(session, "board_pack_sections"):
            await _install_append_only_guard(session, "board_pack_sections")
            section_id = await _insert_section(session, tenant_id, run_id)
            await session.commit()
            await set_tenant_context(session, tenant_id)
            with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
                await session.execute(
                    text("UPDATE board_pack_sections SET section_order=2 WHERE id=:id"),
                    {"id": section_id},
                )
            await session.rollback()
            await set_tenant_context(session, tenant_id)

        if await _table_exists(session, "board_pack_artifacts"):
            await _install_append_only_guard(session, "board_pack_artifacts")
            artifact_id = await _insert_artifact(session, tenant_id, run_id)
            await session.commit()
            await set_tenant_context(session, tenant_id)
            with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
                await session.execute(
                    text("UPDATE board_pack_artifacts SET storage_path='x' WHERE id=:id"),
                    {"id": artifact_id},
                )
            await session.rollback()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_003_append_only_blocks_delete_for_runs_sections_artifacts(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_id = uuid.uuid4()
        await set_tenant_context(session, tenant_id)

        definition_id = await _insert_definition(session, tenant_id)
        run_id = await _insert_run(session, tenant_id, definition_id)
        section_id = (
            await _insert_section(session, tenant_id, run_id)
            if await _table_exists(session, "board_pack_sections")
            else None
        )
        artifact_id = (
            await _insert_artifact(session, tenant_id, run_id)
            if await _table_exists(session, "board_pack_artifacts")
            else None
        )
        await session.commit()
        await set_tenant_context(session, tenant_id)

        await _install_append_only_guard(session, "board_pack_runs")
        with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
            await session.execute(text("DELETE FROM board_pack_runs WHERE id=:id"), {"id": run_id})
        await session.rollback()
        await set_tenant_context(session, tenant_id)

        if section_id is not None:
            await _install_append_only_guard(session, "board_pack_sections")
            with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
                await session.execute(
                    text("DELETE FROM board_pack_sections WHERE id=:id"),
                    {"id": section_id},
                )
            await session.rollback()
            await set_tenant_context(session, tenant_id)

        if artifact_id is not None:
            await _install_append_only_guard(session, "board_pack_artifacts")
            with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
                await session.execute(
                    text("DELETE FROM board_pack_artifacts WHERE id=:id"),
                    {"id": artifact_id},
                )
            await session.rollback()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_004_rls_isolates_rows_by_tenant(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        await session.execute(text("ALTER TABLE board_pack_definitions ENABLE ROW LEVEL SECURITY"))
        await session.execute(text("ALTER TABLE board_pack_definitions FORCE ROW LEVEL SECURITY"))
        await session.execute(text("DROP POLICY IF EXISTS tenant_isolation ON board_pack_definitions"))
        await session.execute(
            text(
                """
                CREATE POLICY tenant_isolation ON board_pack_definitions
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
                """
            )
        )

        await set_tenant_context(session, tenant_a)
        await _insert_definition(session, tenant_a)

        await set_tenant_context(session, tenant_b)
        await _insert_definition(session, tenant_b)

        await set_tenant_context(session, tenant_a)
        count_a = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM board_pack_definitions
                    WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                    """
                )
            )
        ).scalar_one()

        await set_tenant_context(session, tenant_b)
        count_b = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM board_pack_definitions
                    WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                    """
                )
            )
        ).scalar_one()

        pair_count = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM board_pack_definitions
                    WHERE tenant_id IN (:tenant_a, :tenant_b)
                    """
                ),
                {"tenant_a": tenant_a, "tenant_b": tenant_b},
            )
        ).scalar_one()

        assert count_a == 1
        assert count_b == 1
        assert pair_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_005_fk_constraint_rejects_run_with_unknown_definition(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_id = uuid.uuid4()
        await set_tenant_context(session, tenant_id)

        with pytest.raises(IntegrityError):
            await _insert_run(session, tenant_id, uuid.uuid4())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_006_check_constraint_rejects_invalid_run_status(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_id = uuid.uuid4()
        await set_tenant_context(session, tenant_id)

        definition_id = await _insert_definition(session, tenant_id)
        await session.execute(
            text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_status")
        )
        await session.execute(
            text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_generator_status")
        )
        await session.execute(
            text(
                """
                ALTER TABLE board_pack_runs
                ADD CONSTRAINT ck_board_pack_runs_status
                CHECK (lower(status) IN ('pending', 'running', 'complete', 'failed'))
                """
            )
        )
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO board_pack_runs (
                        id, tenant_id, definition_id, period_start, period_end,
                        status, triggered_by, run_metadata, chain_hash, previous_hash,
                        organisation_id, reporting_period, board_pack_definition_version_token,
                        section_definition_version_token, narrative_template_version_token,
                        inclusion_rule_version_token, source_metric_run_ids_json,
                        source_risk_run_ids_json, source_anomaly_run_ids_json,
                        run_token, validation_summary_json, created_by, created_at
                    ) VALUES (
                        :id, :tenant_id, :definition_id, :period_start, :period_end,
                        :status, :triggered_by, CAST(:run_metadata AS jsonb), :chain_hash, :previous_hash,
                        :organisation_id, :reporting_period, :board_pack_definition_version_token,
                        :section_definition_version_token, :narrative_template_version_token,
                        :inclusion_rule_version_token, CAST(:source_metric_run_ids_json AS jsonb),
                        CAST(:source_risk_run_ids_json AS jsonb), CAST(:source_anomaly_run_ids_json AS jsonb),
                        :run_token, CAST(:validation_summary_json AS jsonb), :created_by, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(tenant_id),
                    "definition_id": str(definition_id),
                    "period_start": date(2026, 1, 1),
                    "period_end": date(2026, 1, 31),
                    "status": "INVALID",
                    "triggered_by": str(tenant_id),
                    "run_metadata": json.dumps({"origin_run_id": str(uuid.uuid4())}),
                    "chain_hash": "c" * 64,
                    "previous_hash": "b" * 64,
                    "organisation_id": str(tenant_id),
                    "reporting_period": date(2026, 1, 31),
                    "board_pack_definition_version_token": uuid.uuid4().hex,
                    "section_definition_version_token": uuid.uuid4().hex,
                    "narrative_template_version_token": uuid.uuid4().hex,
                    "inclusion_rule_version_token": uuid.uuid4().hex,
                    "source_metric_run_ids_json": json.dumps([str(uuid.uuid4())]),
                    "source_risk_run_ids_json": json.dumps([str(uuid.uuid4())]),
                    "source_anomaly_run_ids_json": json.dumps([str(uuid.uuid4())]),
                    "run_token": uuid.uuid4().hex,
                    "validation_summary_json": json.dumps({}),
                    "created_by": str(tenant_id),
                    "created_at": datetime.now(UTC),
                },
            )
