from __future__ import annotations

import uuid

import asyncpg
import pytest

from tests.integration.observability_phase3_helpers import OBSERVABILITY_TABLES


async def _configure_probe_role(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        DO $$
        BEGIN
          CREATE ROLE rls_observability_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    await conn.execute("GRANT USAGE ON SCHEMA public TO rls_observability_probe_user")
    await conn.execute(
        "GRANT SELECT, INSERT ON observability_run_registry TO rls_observability_probe_user"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_observability_registry_row(
    observability_phase3_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        await conn.execute(
            """
            INSERT INTO observability_run_registry (
                id, tenant_id, chain_hash, previous_hash, module_code,
                run_id, run_token, version_token_snapshot_json,
                upstream_dependencies_json, execution_time_ms, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'equity_engine',
                $3, 'rtok', '{}'::jsonb, '[]'::jsonb, 1, 'discovered', $4
            )
            """,
            uuid.uuid4(),
            tenant_id,
            uuid.uuid4(),
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_observability_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM observability_run_registry")
        assert count >= 1
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_observability_registry_row(
    observability_phase3_db_url: str,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_b}'")
        await conn.execute(
            """
            INSERT INTO observability_run_registry (
                id, tenant_id, chain_hash, previous_hash, module_code,
                run_id, run_token, version_token_snapshot_json,
                upstream_dependencies_json, execution_time_ms, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'equity_engine',
                $3, 'rtok_b', '{}'::jsonb, '[]'::jsonb, 1, 'discovered', $4
            )
            """,
            uuid.uuid4(),
            tenant_b,
            uuid.uuid4(),
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_observability_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM observability_run_registry")
        assert count == 0
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_observability_tables(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(OBSERVABILITY_TABLES),
        )
        assert len(rows) == len(OBSERVABILITY_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()

