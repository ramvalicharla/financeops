from __future__ import annotations

import asyncpg
import pytest

from tests.integration.ratio_variance_phase1f4_helpers import RATIO_TABLES

EXPECTED_CONSTRAINTS = (
    "ck_metric_definitions_formula_type",
    "ck_metric_definitions_directionality",
    "ck_metric_definitions_status",
    "uq_metric_definitions_version_token",
    "ck_variance_definitions_comparison_type",
    "ck_variance_definitions_status",
    "ck_trend_definitions_trend_type",
    "ck_trend_definitions_window_size",
    "ck_trend_definitions_status",
    "ck_materiality_rules_status",
    "uq_metric_runs_tenant_token",
    "ck_metric_runs_status",
    "ck_metric_runs_requires_input_reference",
)

EXPECTED_INDEXES = (
    "idx_metric_definitions_lookup",
    "uq_metric_definitions_one_active",
    "idx_metric_definition_components_metric",
    "idx_variance_definitions_lookup",
    "uq_variance_definitions_one_active",
    "idx_trend_definitions_lookup",
    "uq_trend_definitions_one_active",
    "idx_materiality_rules_lookup",
    "uq_materiality_rules_one_active",
    "idx_metric_runs_lookup",
    "idx_metric_runs_token",
    "idx_metric_results_run",
    "idx_variance_results_run",
    "idx_trend_results_run",
    "idx_metric_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0016_applies_cleanly_on_fresh_db(ratio_phase1f4_db_url: str) -> None:
    conn = await asyncpg.connect(
        ratio_phase1f4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0019_phase1f7_board_pack"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0016_creates_ratio_tables(ratio_phase1f4_db_url: str) -> None:
    conn = await asyncpg.connect(
        ratio_phase1f4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(RATIO_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(RATIO_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0016_enables_forces_rls_and_triggers(
    ratio_phase1f4_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        ratio_phase1f4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(RATIO_TABLES),
        )
        assert len(rows) == len(RATIO_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True

        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_metric_%'
               OR conname LIKE 'ck_variance_%'
               OR conname LIKE 'ck_trend_%'
               OR conname LIKE 'ck_materiality_%'
               OR conname LIKE 'uq_metric_%'
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
        assert "trg_ratio_metric_definitions_validate_supersession" in trigger_names
        assert "trg_ratio_variance_definitions_validate_supersession" in trigger_names
        assert "trg_ratio_trend_definitions_validate_supersession" in trigger_names
        assert "trg_ratio_materiality_rules_validate_supersession" in trigger_names
        for table in RATIO_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()
