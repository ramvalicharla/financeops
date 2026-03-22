from __future__ import annotations

import asyncpg
import pytest

from tests.integration.equity_phase2_7_helpers import EQUITY_TABLES


EXPECTED_CONSTRAINTS = (
    "uq_equity_statement_definitions_version_token",
    "ck_equity_statement_definitions_currency_basis",
    "ck_equity_statement_definitions_status",
    "uq_equity_line_definitions_version_token",
    "ck_equity_line_definitions_order",
    "ck_equity_line_definitions_line_type",
    "ck_equity_line_definitions_status",
    "uq_equity_rollforward_rule_definitions_version_token",
    "ck_equity_rollforward_rule_definitions_type",
    "ck_equity_rollforward_rule_definitions_status",
    "uq_equity_source_mappings_version_token",
    "ck_equity_source_mappings_source_type",
    "ck_equity_source_mappings_status",
    "uq_equity_runs_tenant_token",
    "ck_equity_runs_status",
    "uq_equity_line_results_line_no",
    "uq_equity_statement_results_run",
    "ck_equity_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_equity_statement_definitions_lookup",
    "uq_equity_statement_definitions_one_active",
    "idx_equity_line_definitions_lookup",
    "uq_equity_line_definitions_one_active",
    "idx_equity_rollforward_rule_definitions_lookup",
    "uq_equity_rollforward_rule_definitions_one_active",
    "idx_equity_source_mappings_lookup",
    "uq_equity_source_mappings_one_active",
    "idx_equity_runs_lookup",
    "idx_equity_line_results_run",
    "idx_equity_statement_results_run",
    "idx_equity_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0024_applies_cleanly_on_fresh_db(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0024_creates_expected_equity_tables(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
              AND table_name = ANY($1::text[])
            ORDER BY table_name
            """,
            list(EQUITY_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(EQUITY_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0024_creates_constraints_indexes_and_triggers(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'uq_equity_%'
               OR conname LIKE 'ck_equity_%'
            """
        )
        names = {row["conname"] for row in constraints}
        for expected in EXPECTED_CONSTRAINTS:
            assert expected in names

        indexes = await conn.fetch("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
        index_names = {row["indexname"] for row in indexes}
        for expected in EXPECTED_INDEXES:
            assert expected in index_names

        triggers = await conn.fetch(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgname"
        )
        trigger_names = {row["tgname"] for row in triggers}
        assert "trg_equity_stmt_defs_validate_supersession" in trigger_names
        assert "trg_equity_line_defs_validate_supersession" in trigger_names
        assert "trg_equity_rule_defs_validate_supersession" in trigger_names
        assert "trg_equity_source_maps_validate_supersession" in trigger_names
        for table in EQUITY_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0024_enables_and_forces_rls_on_equity_tables(
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
