from __future__ import annotations

import uuid

import asyncpg
import pytest

from financeops.db.append_only import APPEND_ONLY_TABLES


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_equity_statement_definitions(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        row_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO equity_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                statement_code, statement_name, reporting_currency_basis,
                ownership_basis_flag, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), $3,
                'EQ_MAIN', 'Equity Main', 'source_currency',
                false, 'v1', DATE '2026-01-01',
                NULL, 'active', $4
            )
            """,
            row_id,
            tenant_id,
            org_id,
            user_id,
        )

        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE equity_statement_definitions SET statement_name = $1 WHERE id = $2",
                "Changed",
                row_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_equity_runs(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        row_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO equity_runs (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_period, statement_definition_version_token,
                line_definition_version_token, rollforward_rule_version_token,
                source_mapping_version_token, consolidation_run_ref_nullable,
                fx_translation_run_ref_nullable, ownership_consolidation_run_ref_nullable,
                run_token, run_status, validation_summary_json, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), $3,
                DATE '2026-01-31', 'stmt_v1',
                'line_v1', 'rule_v1',
                'map_v1', NULL,
                NULL, NULL,
                'run_tok_v1', 'created', '{}'::jsonb, $4
            )
            """,
            row_id,
            tenant_id,
            org_id,
            user_id,
        )

        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE equity_runs SET run_status = $1 WHERE id = $2",
                "completed",
                row_id,
            )
    finally:
        await conn.close()


def test_append_only_registry_includes_equity_tables() -> None:
    expected_tables = {
        "equity_statement_definitions",
        "equity_line_definitions",
        "equity_rollforward_rule_definitions",
        "equity_source_mappings",
        "equity_runs",
        "equity_line_results",
        "equity_statement_results",
        "equity_evidence_links",
    }
    assert expected_tables.issubset(set(APPEND_ONLY_TABLES))
