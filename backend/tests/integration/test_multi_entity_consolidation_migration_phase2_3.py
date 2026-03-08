from __future__ import annotations

import asyncpg
import pytest

from tests.integration.multi_entity_consolidation_phase2_3_helpers import (
    MULTI_ENTITY_CONSOLIDATION_TABLES,
)


EXPECTED_CONSTRAINTS = (
    "uq_entity_hierarchies_version_token",
    "ck_entity_hierarchies_type",
    "ck_entity_hierarchies_status",
    "ck_entity_hierarchy_nodes_level",
    "ck_entity_hierarchy_nodes_status",
    "uq_consolidation_scopes_version_token",
    "ck_consolidation_scopes_status",
    "uq_consolidation_rule_definitions_version_token",
    "ck_consolidation_rule_definitions_type",
    "ck_consolidation_rule_definitions_status",
    "uq_intercompany_mapping_rules_version_token",
    "ck_intercompany_mapping_rules_status",
    "uq_consolidation_adjustment_definitions_version_token",
    "ck_consolidation_adjustment_definitions_type",
    "ck_consolidation_adjustment_definitions_status",
    "uq_multi_entity_consolidation_runs_tenant_token",
    "ck_multi_entity_consolidation_runs_status",
    "ck_multi_entity_consolidation_runs_sources_required",
)

EXPECTED_INDEXES = (
    "idx_entity_hierarchies_lookup",
    "uq_entity_hierarchies_one_active",
    "idx_entity_hierarchy_nodes_lookup",
    "uq_entity_hierarchy_nodes_one_active",
    "idx_entity_hierarchy_nodes_parent",
    "idx_consolidation_scopes_lookup",
    "uq_consolidation_scopes_one_active",
    "idx_consolidation_rule_definitions_lookup",
    "uq_consolidation_rule_definitions_one_active",
    "idx_intercompany_mapping_rules_lookup",
    "uq_intercompany_mapping_rules_one_active",
    "idx_consolidation_adjustment_definitions_lookup",
    "uq_consolidation_adjustment_definitions_one_active",
    "idx_multi_entity_consolidation_runs_lookup",
    "idx_multi_entity_consolidation_runs_token",
    "idx_multi_entity_consolidation_metric_results_run",
    "idx_multi_entity_consolidation_variance_results_run",
    "idx_multi_entity_consolidation_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0020_applies_cleanly_on_fresh_db(
    multi_entity_phase2_3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        multi_entity_phase2_3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0023_phase2_6_cash_flow"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0020_creates_all_expected_tables_and_rls(
    multi_entity_phase2_3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        multi_entity_phase2_3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(MULTI_ENTITY_CONSOLIDATION_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(MULTI_ENTITY_CONSOLIDATION_TABLES)

        rls_rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(MULTI_ENTITY_CONSOLIDATION_TABLES),
        )
        assert len(rls_rows) == len(MULTI_ENTITY_CONSOLIDATION_TABLES)
        for row in rls_rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0020_creates_constraints_indexes_and_triggers(
    multi_entity_phase2_3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        multi_entity_phase2_3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_entity_hierarchies_%'
               OR conname LIKE 'uq_entity_hierarchies_%'
               OR conname LIKE 'ck_entity_hierarchy_nodes_%'
               OR conname LIKE 'ck_consolidation_%'
               OR conname LIKE 'uq_consolidation_%'
               OR conname LIKE 'ck_intercompany_%'
               OR conname LIKE 'uq_intercompany_%'
               OR conname LIKE 'ck_multi_entity_consolidation_%'
               OR conname LIKE 'uq_multi_entity_consolidation_%'
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
        assert "trg_entity_hierarchies_validate_supersession" in trigger_names
        assert "trg_entity_hierarchy_nodes_validate_integrity" in trigger_names
        assert "trg_consolidation_scopes_validate_supersession" in trigger_names
        assert "trg_consolidation_rule_definitions_validate_supersession" in trigger_names
        assert "trg_intercompany_mapping_rules_validate_supersession" in trigger_names
        assert "trg_consolidation_adjustment_definitions_validate_supersession" in trigger_names
        for table in MULTI_ENTITY_CONSOLIDATION_TABLES:
            assert f"trg_append_only_{table}" in trigger_names
    finally:
        await conn.close()
