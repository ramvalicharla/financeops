from __future__ import annotations

import asyncpg
import pytest

from tests.integration.board_pack_phase1f7_helpers import BOARD_PACK_TABLES

EXPECTED_CONSTRAINTS = (
    "uq_board_pack_definitions_version_token",
    "ck_board_pack_definitions_status",
    "uq_board_pack_section_definitions_version_token",
    "ck_board_pack_section_definitions_type",
    "ck_board_pack_section_definitions_status",
    "uq_narrative_templates_version_token",
    "ck_narrative_templates_type",
    "ck_narrative_templates_status",
    "uq_board_pack_inclusion_rules_version_token",
    "ck_board_pack_inclusion_rules_type",
    "ck_board_pack_inclusion_rules_status",
    "uq_board_pack_runs_tenant_token",
    "ck_board_pack_runs_status",
    "ck_board_pack_runs_metric_sources_required",
    "ck_board_pack_runs_risk_sources_required",
    "ck_board_pack_runs_anomaly_sources_required",
    "uq_board_pack_results_run_id",
    "ck_board_pack_results_health",
    "ck_board_pack_results_status",
    "uq_board_pack_section_results_order",
    "uq_board_pack_narrative_blocks_order",
    "ck_board_pack_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_board_pack_definitions_lookup",
    "uq_board_pack_definitions_one_active",
    "idx_board_pack_section_definitions_lookup",
    "uq_board_pack_section_definitions_one_active",
    "idx_narrative_templates_lookup",
    "uq_narrative_templates_one_active",
    "idx_board_pack_inclusion_rules_lookup",
    "uq_board_pack_inclusion_rules_one_active",
    "idx_board_pack_runs_lookup",
    "idx_board_pack_runs_token",
    "idx_board_pack_results_run",
    "idx_board_pack_section_results_run",
    "idx_board_pack_narrative_blocks_run",
    "idx_board_pack_evidence_links_run",
    "idx_board_pack_evidence_links_section",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0019_applies_cleanly_on_fresh_db(
    board_pack_phase1f7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        board_pack_phase1f7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0021_phase2_4_fx_translation"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0019_creates_all_expected_board_pack_tables(
    board_pack_phase1f7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        board_pack_phase1f7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(BOARD_PACK_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(BOARD_PACK_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0019_creates_expected_constraints_indexes_triggers_and_rls(
    board_pack_phase1f7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        board_pack_phase1f7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(BOARD_PACK_TABLES),
        )
        assert len(rows) == len(BOARD_PACK_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True

        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_board_pack_%'
               OR conname LIKE 'uq_board_pack_%'
               OR conname LIKE 'ck_narrative_templates_%'
               OR conname LIKE 'uq_narrative_templates_%'
            """
        )
        constraint_names = {row["conname"] for row in constraints}
        for name in EXPECTED_CONSTRAINTS:
            assert name in constraint_names

        indexes = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname='public'
            """
        )
        index_names = {row["indexname"] for row in indexes}
        for name in EXPECTED_INDEXES:
            assert name in index_names

        triggers = await conn.fetch(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE NOT tgisinternal
            """
        )
        trigger_names = {row["tgname"] for row in triggers}
        assert "trg_board_pack_definitions_validate_supersession" in trigger_names
        assert "trg_board_pack_section_definitions_validate_supersession" in trigger_names
        assert "trg_narrative_templates_validate_supersession" in trigger_names
        assert "trg_board_pack_inclusion_rules_validate_supersession" in trigger_names
        for table in BOARD_PACK_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()
