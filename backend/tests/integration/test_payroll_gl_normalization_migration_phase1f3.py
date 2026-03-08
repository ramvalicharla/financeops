from __future__ import annotations

import asyncpg
import pytest

from tests.integration.normalization_phase1f3_helpers import NORMALIZATION_TABLES

EXPECTED_CONSTRAINTS: tuple[str, ...] = (
    "uq_normalization_sources_tenant_code",
    "ck_normalization_sources_status",
    "uq_normalization_source_versions_source_no",
    "uq_normalization_source_versions_source_token",
    "ck_normalization_source_versions_status",
    "ck_normalization_mappings_type",
    "ck_normalization_mappings_confidence",
    "uq_normalization_runs_tenant_token",
    "ck_normalization_runs_type",
    "ck_normalization_runs_status",
    "uq_payroll_normalized_lines_row_metric",
    "ck_payroll_normalized_lines_status",
    "uq_gl_normalized_lines_run_row",
    "ck_gl_normalized_lines_status",
    "ck_normalization_exceptions_severity",
    "ck_normalization_exceptions_resolution_status",
    "ck_normalization_evidence_links_line_type",
    "ck_normalization_evidence_links_evidence_type",
)

EXPECTED_INDEXES: tuple[str, ...] = (
    "idx_normalization_sources_tenant",
    "idx_normalization_sources_family_code",
    "idx_normalization_source_versions_source",
    "uq_normalization_source_versions_one_active",
    "idx_normalization_mappings_source_version",
    "idx_normalization_mappings_field",
    "idx_normalization_runs_source_period",
    "idx_normalization_runs_token",
    "idx_payroll_normalized_lines_run",
    "idx_payroll_normalized_lines_employee_period",
    "idx_payroll_normalized_lines_metric",
    "idx_gl_normalized_lines_run",
    "idx_gl_normalized_lines_account_period",
    "idx_normalization_exceptions_run",
    "idx_normalization_exceptions_severity",
    "idx_normalization_evidence_links_run_line",
    "idx_normalization_evidence_links_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0014_applies_cleanly_on_fresh_db(
    normalization_phase1f3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        normalization_phase1f3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0024_phase2_7_equity_engine"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0014_creates_expected_normalization_tables(
    normalization_phase1f3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        normalization_phase1f3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(NORMALIZATION_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(NORMALIZATION_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0014_enables_and_forces_rls_on_all_normalization_tables(
    normalization_phase1f3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        normalization_phase1f3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(NORMALIZATION_TABLES),
        )
        assert len(rows) == len(NORMALIZATION_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0014_creates_expected_constraints_indexes_and_triggers(
    normalization_phase1f3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        normalization_phase1f3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_normalization_%'
               OR conname LIKE 'uq_normalization_%'
               OR conname LIKE 'ck_payroll_%'
               OR conname LIKE 'uq_payroll_%'
               OR conname LIKE 'ck_gl_%'
               OR conname LIKE 'uq_gl_%'
            """
        )
        constraint_names = {row["conname"] for row in constraints}
        for name in EXPECTED_CONSTRAINTS:
            assert name in constraint_names

        indexes = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
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
        assert "trg_normalization_source_versions_validate_supersession" in trigger_names
        for table_name in NORMALIZATION_TABLES:
            assert f"trg_append_only_{table_name}" in trigger_names
    finally:
        await conn.close()

