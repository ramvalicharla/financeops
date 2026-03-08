from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest

from tests.integration.equity_phase2_7_helpers import EQUITY_TABLES


async def _configure_probe_role(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        DO $$
        BEGIN
          CREATE ROLE rls_equity_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    await conn.execute("GRANT USAGE ON SCHEMA public TO rls_equity_probe_user")
    await conn.execute(
        "GRANT SELECT, INSERT ON equity_statement_definitions TO rls_equity_probe_user"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_equity_definition(
    equity_phase2_7_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        await conn.execute(
            """
            INSERT INTO equity_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id, statement_code,
                statement_name, reporting_currency_basis, ownership_basis_flag,
                version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "EQ_RLS_1",
            "EQ RLS 1",
            "source_currency",
            False,
            "tok_rls_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_equity_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM equity_statement_definitions")
        assert count >= 1
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_equity_definition(
    equity_phase2_7_db_url: str,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    org_b = uuid.uuid4()
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_b}'")
        await conn.execute(
            """
            INSERT INTO equity_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id, statement_code,
                statement_name, reporting_currency_basis, ownership_basis_flag,
                version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_b,
            "b" * 64,
            "0" * 64,
            org_b,
            "EQ_RLS_2",
            "EQ RLS 2",
            "source_currency",
            False,
            "tok_rls_2",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_equity_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM equity_statement_definitions")
        assert count == 0
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_equity_tables(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(EQUITY_TABLES),
        )
        assert len(rows) == len(EQUITY_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()
