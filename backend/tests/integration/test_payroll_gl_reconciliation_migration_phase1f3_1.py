from __future__ import annotations

import asyncpg
import pytest

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    PAYROLL_GL_RECON_TABLES,
)

EXPECTED_CONSTRAINTS: tuple[str, ...] = (
    "ck_payroll_gl_recon_mappings_status",
    "ck_payroll_gl_recon_rules_type",
    "ck_payroll_gl_recon_rules_status",
    "uq_payroll_gl_recon_runs_tenant_token",
    "ck_payroll_gl_recon_runs_status",
    "uq_payroll_gl_recon_run_scopes_code",
)

EXPECTED_INDEXES: tuple[str, ...] = (
    "idx_payroll_gl_recon_mappings_lookup",
    "uq_payroll_gl_recon_mappings_one_active",
    "idx_payroll_gl_recon_rules_lookup",
    "uq_payroll_gl_recon_rules_one_active",
    "idx_payroll_gl_recon_runs_lookup",
    "idx_payroll_gl_recon_runs_session",
    "idx_payroll_gl_recon_run_scopes_run",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0015_applies_cleanly_on_fresh_db(
    payroll_gl_recon_phase1f3_1_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        payroll_gl_recon_phase1f3_1_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        assert version == "0018_phase1f6_anomaly_pattern"
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0015_creates_expected_payroll_gl_reconciliation_tables(
    payroll_gl_recon_phase1f3_1_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        payroll_gl_recon_phase1f3_1_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
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
            list(PAYROLL_GL_RECON_TABLES),
        )
        assert [row["table_name"] for row in rows] == sorted(PAYROLL_GL_RECON_TABLES)
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0015_enables_and_forces_rls_on_all_payroll_gl_reconciliation_tables(
    payroll_gl_recon_phase1f3_1_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        payroll_gl_recon_phase1f3_1_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(PAYROLL_GL_RECON_TABLES),
        )
        assert len(rows) == len(PAYROLL_GL_RECON_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0015_creates_expected_constraints_indexes_and_triggers(
    payroll_gl_recon_phase1f3_1_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        payroll_gl_recon_phase1f3_1_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        constraints = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conname LIKE 'ck_payroll_gl_recon_%'
               OR conname LIKE 'uq_payroll_gl_recon_%'
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
        assert "trg_payroll_gl_recon_mappings_validate_supersession" in trigger_names
        assert "trg_payroll_gl_recon_rules_validate_supersession" in trigger_names
        for table_name in PAYROLL_GL_RECON_TABLES:
            assert f"trg_append_only_{table_name}" in trigger_names
    finally:
        await conn.close()

