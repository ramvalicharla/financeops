from __future__ import annotations

import asyncpg
import pytest

from tests.integration.fx_translation_phase2_4_helpers import FX_TRANSLATION_TABLES


EXPECTED_CONSTRAINTS = (
    "uq_reporting_currency_definitions_version_token",
    "ck_reporting_currency_definitions_status",
    "uq_fx_translation_rule_definitions_version_token",
    "ck_fx_translation_rule_definitions_status",
    "uq_fx_rate_selection_policies_version_token",
    "ck_fx_rate_selection_policies_rate_type",
    "ck_fx_rate_selection_policies_status",
    "uq_fx_translation_runs_tenant_token",
    "ck_fx_translation_runs_status",
    "ck_fx_translation_runs_sources_required",
    "uq_fx_translated_metric_results_line_no",
    "uq_fx_translated_variance_results_line_no",
    "ck_fx_translated_variance_results_type",
    "ck_fx_translation_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_reporting_currency_definitions_lookup",
    "uq_reporting_currency_definitions_one_active_scope",
    "idx_fx_translation_rule_definitions_lookup",
    "uq_fx_translation_rule_definitions_one_active",
    "idx_fx_rate_selection_policies_lookup",
    "uq_fx_rate_selection_policies_one_active",
    "idx_fx_translation_runs_lookup",
    "idx_fx_translation_runs_token",
    "idx_fx_translated_metric_results_run",
    "idx_fx_translated_metric_results_source",
    "idx_fx_translated_variance_results_run",
    "idx_fx_translated_variance_results_source",
    "idx_fx_translation_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0021_applies_cleanly_on_fresh_db(
    fx_translation_phase2_4_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0024_phase2_7_equity_engine"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0021_creates_expected_fx_translation_tables_and_rls(
    fx_translation_phase2_4_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(FX_TRANSLATION_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(FX_TRANSLATION_TABLES)

        rls_rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(FX_TRANSLATION_TABLES),
        )
        assert len(rls_rows) == len(FX_TRANSLATION_TABLES)
        for row in rls_rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0021_creates_expected_constraints_indexes_and_triggers(
    fx_translation_phase2_4_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'uq_reporting_currency_definitions_%'
               OR conname LIKE 'ck_reporting_currency_definitions_%'
               OR conname LIKE 'uq_fx_translation_rule_definitions_%'
               OR conname LIKE 'ck_fx_translation_rule_definitions_%'
               OR conname LIKE 'uq_fx_rate_selection_policies_%'
               OR conname LIKE 'ck_fx_rate_selection_policies_%'
               OR conname LIKE 'uq_fx_translation_runs_%'
               OR conname LIKE 'ck_fx_translation_runs_%'
               OR conname LIKE 'uq_fx_translated_metric_results_%'
               OR conname LIKE 'uq_fx_translated_variance_results_%'
               OR conname LIKE 'ck_fx_translated_variance_results_%'
               OR conname LIKE 'ck_fx_translation_evidence_links_%'
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
        assert "trg_reporting_currency_definitions_validate_supersession" in trigger_names
        assert "trg_fx_translation_rule_definitions_validate_supersession" in trigger_names
        assert "trg_fx_rate_selection_policies_validate_supersession" in trigger_names
        for table in FX_TRANSLATION_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()


