from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest

from tests.integration.ownership_consolidation_phase2_5_helpers import (
    OWNERSHIP_CONSOLIDATION_TABLES,
)


async def _configure_probe_role(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        DO $$
        BEGIN
          CREATE ROLE rls_ownership_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    await conn.execute("GRANT USAGE ON SCHEMA public TO rls_ownership_probe_user")
    await conn.execute(
        "GRANT SELECT, INSERT ON ownership_structure_definitions TO rls_ownership_probe_user"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_ownership_structure(
    ownership_phase2_5_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        await conn.execute(
            """
            INSERT INTO ownership_structure_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                ownership_structure_code, ownership_structure_name, hierarchy_scope_ref,
                ownership_basis_type, version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_id,
            "a" * 64,
            "0" * 64,
            tenant_id,
            "grp_own_1",
            "Group Own",
            "scope-main",
            "equity_percentage",
            "tok_own_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_ownership_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM ownership_structure_definitions")
        assert count >= 1
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_ownership_structure(
    ownership_phase2_5_db_url: str,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_b}'")
        await conn.execute(
            """
            INSERT INTO ownership_structure_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                ownership_structure_code, ownership_structure_name, hierarchy_scope_ref,
                ownership_basis_type, version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_b,
            "b" * 64,
            "0" * 64,
            tenant_b,
            "grp_own_2",
            "Group Own 2",
            "scope-main",
            "equity_percentage",
            "tok_own_2",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_ownership_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM ownership_structure_definitions")
        assert count == 0
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_ownership_tables(
    ownership_phase2_5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(OWNERSHIP_CONSOLIDATION_TABLES),
        )
        assert len(rows) == len(OWNERSHIP_CONSOLIDATION_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()
