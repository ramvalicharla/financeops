from __future__ import annotations

import asyncpg
import pytest

from tests.integration.reconciliation_phase1f2_helpers import RECON_TABLES


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0013_applies_cleanly_on_fresh_db(
    recon_phase1f2_db_url: str,
) -> None:
    conn = await asyncpg.connect(recon_phase1f2_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0024_phase2_7_equity_engine"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0013_creates_reconciliation_bridge_tables(
    recon_phase1f2_db_url: str,
) -> None:
    conn = await asyncpg.connect(recon_phase1f2_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
              AND table_name = ANY($1::text[])
            ORDER BY table_name
            """,
            list(RECON_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(RECON_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0013_enables_and_forces_rls_on_all_reconciliation_bridge_tables(
    recon_phase1f2_db_url: str,
) -> None:
    conn = await asyncpg.connect(recon_phase1f2_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(RECON_TABLES),
        )
        assert len(rows) == len(RECON_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()

