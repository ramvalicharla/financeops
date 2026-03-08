from __future__ import annotations

import asyncpg
import pytest

from tests.integration.cash_flow_phase2_6_helpers import CASH_FLOW_TABLES


EXPECTED_CONSTRAINTS = (
    "uq_cash_flow_statement_definitions_version_token",
    "ck_cash_flow_statement_definitions_method_type",
    "ck_cash_flow_statement_definitions_status",
    "uq_cash_flow_line_mappings_version_token",
    "ck_cash_flow_line_mappings_line_order",
    "ck_cash_flow_line_mappings_method_type",
    "ck_cash_flow_line_mappings_aggregation_type",
    "ck_cash_flow_line_mappings_ownership_applicability",
    "ck_cash_flow_line_mappings_fx_applicability",
    "ck_cash_flow_line_mappings_status",
    "uq_cash_flow_bridge_rule_definitions_version_token",
    "ck_cash_flow_bridge_rule_definitions_status",
    "uq_cash_flow_runs_tenant_token",
    "ck_cash_flow_runs_status",
    "uq_cash_flow_line_results_line_no",
    "ck_cash_flow_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_cash_flow_statement_definitions_lookup",
    "uq_cash_flow_statement_definitions_one_active",
    "idx_cash_flow_line_mappings_lookup",
    "uq_cash_flow_line_mappings_one_active",
    "idx_cash_flow_bridge_rule_definitions_lookup",
    "uq_cash_flow_bridge_rule_definitions_one_active",
    "idx_cash_flow_runs_lookup",
    "idx_cash_flow_runs_token",
    "idx_cash_flow_line_results_run",
    "idx_cash_flow_line_results_section",
    "idx_cash_flow_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0023_applies_cleanly_on_fresh_db(
    cash_flow_phase2_6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0025_phase3_observability_engine"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0023_creates_expected_cash_flow_tables(
    cash_flow_phase2_6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(CASH_FLOW_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(CASH_FLOW_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0023_creates_constraints_indexes_and_triggers(
    cash_flow_phase2_6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'uq_cash_flow_%'
               OR conname LIKE 'ck_cash_flow_%'
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
        assert "trg_cash_flow_stmt_defs_validate_supersession" in trigger_names
        assert "trg_cash_flow_line_maps_validate_supersession" in trigger_names
        assert "trg_cash_flow_bridge_rules_validate_supersession" in trigger_names
        for table in CASH_FLOW_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0023_enables_and_forces_rls_on_cash_flow_tables(
    cash_flow_phase2_6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(CASH_FLOW_TABLES),
        )
        assert len(rows) == len(CASH_FLOW_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()

