from __future__ import annotations

import asyncpg
import pytest

from tests.integration.anomaly_pattern_phase1f6_helpers import ANOMALY_TABLES

EXPECTED_CONSTRAINTS = (
    "ck_anomaly_definitions_domain",
    "ck_anomaly_definitions_status",
    "uq_anomaly_definitions_version_token",
    "ck_anomaly_pattern_rules_status",
    "uq_anomaly_pattern_rules_version_token",
    "ck_anomaly_persistence_rules_rolling_window",
    "ck_anomaly_persistence_rules_recurrence_threshold",
    "ck_anomaly_persistence_rules_status",
    "uq_anomaly_persistence_rules_version_token",
    "ck_anomaly_correlation_rules_window",
    "ck_anomaly_correlation_rules_min_signal_count",
    "ck_anomaly_correlation_rules_status",
    "uq_anomaly_correlation_rules_version_token",
    "ck_anomaly_statistical_rules_window",
    "ck_anomaly_statistical_rules_baseline_type",
    "ck_anomaly_statistical_rules_z_threshold",
    "ck_anomaly_statistical_rules_status",
    "uq_anomaly_statistical_rules_version_token",
    "uq_anomaly_runs_tenant_token",
    "ck_anomaly_runs_status",
    "ck_anomaly_runs_metric_sources_required",
    "ck_anomaly_runs_variance_sources_required",
    "uq_anomaly_results_line_no",
    "ck_anomaly_results_domain",
    "ck_anomaly_results_severity",
    "ck_anomaly_results_score",
    "ck_anomaly_results_confidence",
    "ck_anomaly_results_persistence",
    "ck_anomaly_contributing_signals_type",
    "ck_anomaly_contributing_signals_weight",
    "ck_anomaly_contributing_signals_score",
    "ck_anomaly_rollforward_events_type",
    "ck_anomaly_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_anomaly_definitions_lookup",
    "uq_anomaly_definitions_one_active",
    "idx_anomaly_pattern_rules_lookup",
    "uq_anomaly_pattern_rules_one_active",
    "idx_anomaly_persistence_rules_lookup",
    "uq_anomaly_persistence_rules_one_active",
    "idx_anomaly_correlation_rules_lookup",
    "uq_anomaly_correlation_rules_one_active",
    "idx_anomaly_statistical_rules_lookup",
    "uq_anomaly_statistical_rules_one_active",
    "idx_anomaly_runs_lookup",
    "idx_anomaly_runs_token",
    "idx_anomaly_results_run",
    "idx_anomaly_results_domain_severity",
    "idx_anomaly_contributing_signals_run",
    "idx_anomaly_rollforward_events_run",
    "idx_anomaly_evidence_links_run",
    "idx_anomaly_evidence_links_result",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0018_applies_cleanly_on_fresh_db(
    anomaly_phase1f6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        anomaly_phase1f6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0024_phase2_7_equity_engine"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0018_creates_all_expected_anomaly_tables(
    anomaly_phase1f6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        anomaly_phase1f6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(ANOMALY_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(ANOMALY_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0018_creates_expected_constraints_indexes_triggers_and_rls(
    anomaly_phase1f6_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        anomaly_phase1f6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(ANOMALY_TABLES),
        )
        assert len(rows) == len(ANOMALY_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True

        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_anomaly_%'
               OR conname LIKE 'uq_anomaly_%'
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
        assert "trg_anomaly_definitions_validate_supersession" in trigger_names
        assert "trg_anomaly_pattern_rules_validate_supersession" in trigger_names
        assert "trg_anomaly_persistence_rules_validate_supersession" in trigger_names
        assert "trg_anomaly_correlation_rules_validate_supersession" in trigger_names
        assert "trg_anomaly_statistical_rules_validate_supersession" in trigger_names
        for table in ANOMALY_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()

