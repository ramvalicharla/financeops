from __future__ import annotations

import asyncpg
import pytest

from tests.integration.ownership_consolidation_phase2_5_helpers import (
    OWNERSHIP_CONSOLIDATION_TABLES,
)


EXPECTED_CONSTRAINTS = (
    "uq_ownership_structure_definitions_version_token",
    "ck_ownership_structure_definitions_basis_type",
    "ck_ownership_structure_definitions_status",
    "ck_ownership_relationships_pct",
    "ck_ownership_relationships_voting_pct",
    "ck_ownership_relationships_status",
    "uq_ownership_consolidation_rule_definitions_version_token",
    "ck_ownership_consolidation_rule_definitions_type",
    "ck_ownership_consolidation_rule_definitions_status",
    "uq_minority_interest_rule_definitions_version_token",
    "ck_minority_interest_rule_definitions_basis_type",
    "ck_minority_interest_rule_definitions_status",
    "uq_ownership_consolidation_runs_tenant_token",
    "ck_ownership_consolidation_runs_status",
    "ck_ownership_consolidation_runs_sources_required",
    "uq_ownership_consolidation_metric_results_line_no",
    "uq_ownership_consolidation_variance_results_line_no",
    "ck_ownership_consolidation_variance_results_type",
    "ck_ownership_consolidation_evidence_links_type",
)

EXPECTED_INDEXES = (
    "idx_ownership_structure_definitions_lookup",
    "uq_ownership_structure_definitions_one_active",
    "idx_ownership_relationships_lookup",
    "uq_ownership_relationships_one_active",
    "idx_ownership_relationships_child_lookup",
    "idx_ownership_consolidation_rule_definitions_lookup",
    "uq_ownership_consolidation_rule_definitions_one_active",
    "idx_minority_interest_rule_definitions_lookup",
    "uq_minority_interest_rule_definitions_one_active",
    "idx_ownership_consolidation_runs_lookup",
    "idx_ownership_consolidation_runs_token",
    "idx_ownership_consolidation_metric_results_run",
    "idx_ownership_consolidation_metric_results_metric",
    "idx_ownership_consolidation_variance_results_run",
    "idx_ownership_consolidation_variance_results_metric",
    "idx_ownership_consolidation_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0022_applies_cleanly_on_fresh_db(
    ownership_phase2_5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0023_phase2_6_cash_flow"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0022_creates_expected_tables_and_rls(
    ownership_phase2_5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(OWNERSHIP_CONSOLIDATION_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(OWNERSHIP_CONSOLIDATION_TABLES)

        rls_rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(OWNERSHIP_CONSOLIDATION_TABLES),
        )
        assert len(rls_rows) == len(OWNERSHIP_CONSOLIDATION_TABLES)
        for row in rls_rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0022_creates_constraints_indexes_and_triggers(
    ownership_phase2_5_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'uq_ownership_%'
               OR conname LIKE 'ck_ownership_%'
               OR conname LIKE 'uq_minority_interest_%'
               OR conname LIKE 'ck_minority_interest_%'
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
        assert "trg_ownership_structure_definitions_validate_supersession" in trigger_names
        assert "trg_ownership_relationships_validate_integrity" in trigger_names
        assert "trg_own_cons_rule_defs_validate_supersession" in trigger_names
        assert "trg_minority_rule_defs_validate_supersession" in trigger_names
        for table in OWNERSHIP_CONSOLIDATION_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()
