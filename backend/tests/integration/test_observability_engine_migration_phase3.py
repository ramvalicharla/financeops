from __future__ import annotations

import asyncpg
import pytest

from tests.integration.observability_phase3_helpers import OBSERVABILITY_TABLES

EXPECTED_CONSTRAINTS = (
    "uq_observability_run_registry_run",
    "ck_observability_run_registry_execution_time",
    "ck_observability_run_registry_status",
    "uq_run_token_diff_definitions_version_token",
    "ck_run_token_diff_definitions_type",
    "ck_run_token_diff_definitions_status",
    "uq_run_token_diff_results_pair_chain",
    "uq_lineage_graph_snapshots_hash",
    "ck_governance_events_type",
    "ck_run_performance_metrics_query_count",
    "ck_run_performance_metrics_execution_time",
    "ck_run_performance_metrics_dependency_depth",
    "uq_observability_runs_operation_token",
    "ck_observability_runs_type",
    "ck_observability_runs_status",
    "ck_observability_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_observability_run_registry_lookup",
    "idx_observability_run_registry_run",
    "idx_run_token_diff_definitions_lookup",
    "uq_run_token_diff_definitions_one_active",
    "idx_run_token_diff_results_lookup",
    "idx_lineage_graph_snapshots_lookup",
    "idx_governance_events_lookup",
    "idx_run_performance_metrics_lookup",
    "idx_observability_runs_lookup",
    "idx_observability_results_lookup",
    "idx_observability_evidence_links_lookup",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0025_applies_cleanly_on_fresh_db(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0025_creates_all_expected_observability_tables(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(OBSERVABILITY_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(OBSERVABILITY_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0025_creates_expected_constraints_indexes_and_triggers(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'uq_observability_%'
               OR conname LIKE 'ck_observability_%'
               OR conname LIKE 'uq_run_token_diff_%'
               OR conname LIKE 'ck_run_token_diff_%'
               OR conname LIKE 'uq_lineage_graph_%'
               OR conname LIKE 'ck_governance_%'
               OR conname LIKE 'ck_run_performance_%'
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
        assert "trg_obs_diff_defs_validate_supersession" in trigger_names
        for table in OBSERVABILITY_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0025_enables_and_forces_rls_on_all_observability_tables(
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

