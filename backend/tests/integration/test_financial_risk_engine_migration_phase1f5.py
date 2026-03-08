from __future__ import annotations

import asyncpg
import pytest

from tests.integration.financial_risk_phase1f5_helpers import FINANCIAL_RISK_TABLES

EXPECTED_CONSTRAINTS = (
    "ck_risk_definitions_domain",
    "ck_risk_definitions_status",
    "uq_risk_definitions_version_token",
    "ck_risk_definition_dependencies_type",
    "ck_risk_definition_dependencies_propagation_factor",
    "ck_risk_definition_dependencies_cap_limit",
    "ck_risk_weight_configurations_scope_type",
    "ck_risk_weight_configurations_weight_value",
    "ck_risk_weight_configurations_status",
    "uq_risk_weight_configurations_version_token",
    "ck_risk_materiality_rules_status",
    "uq_risk_materiality_rules_version_token",
    "uq_risk_runs_tenant_token",
    "ck_risk_runs_status",
    "ck_risk_runs_metric_sources_required",
    "ck_risk_runs_variance_sources_required",
    "ck_risk_runs_trend_sources_array",
    "ck_risk_runs_reconciliation_sources_array",
    "uq_risk_results_line_no",
    "ck_risk_results_domain",
    "ck_risk_results_severity",
    "ck_risk_results_score",
    "ck_risk_results_confidence",
    "ck_risk_results_persistence",
    "ck_risk_contributing_signals_type",
    "ck_risk_contributing_signals_weight",
    "ck_risk_contributing_signals_score",
    "ck_risk_rollforward_events_type",
    "ck_risk_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_risk_definitions_lookup",
    "uq_risk_definitions_one_active",
    "idx_risk_definition_dependencies_risk",
    "idx_risk_definition_dependencies_depends_on",
    "idx_risk_weight_configurations_lookup",
    "uq_risk_weight_configurations_one_active",
    "idx_risk_materiality_rules_lookup",
    "uq_risk_materiality_rules_one_active",
    "idx_risk_runs_lookup",
    "idx_risk_runs_token",
    "idx_risk_results_run",
    "idx_risk_results_domain_severity",
    "idx_risk_contributing_signals_run",
    "idx_risk_rollforward_events_run",
    "idx_risk_evidence_links_run",
    "idx_risk_evidence_links_result",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0017_applies_cleanly_on_fresh_db(
    financial_risk_phase1f5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        financial_risk_phase1f5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0020_phase2_3_multi_entity_con"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0017_creates_financial_risk_tables(
    financial_risk_phase1f5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        financial_risk_phase1f5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(FINANCIAL_RISK_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(FINANCIAL_RISK_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0017_enables_forces_rls_and_triggers(
    financial_risk_phase1f5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        financial_risk_phase1f5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(FINANCIAL_RISK_TABLES),
        )
        assert len(rows) == len(FINANCIAL_RISK_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True

        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_risk_%'
               OR conname LIKE 'uq_risk_%'
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
        assert "trg_risk_definitions_validate_supersession" in trigger_names
        assert "trg_risk_weight_configurations_validate_supersession" in trigger_names
        assert "trg_risk_materiality_rules_validate_supersession" in trigger_names
        assert "trg_risk_definition_dependencies_validate" in trigger_names
        for table in FINANCIAL_RISK_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()
