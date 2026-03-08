from __future__ import annotations

import uuid

import asyncpg
import pytest

from financeops.db.append_only import APPEND_ONLY_TABLES


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_observability_runs(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        row_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO observability_runs (
                id, tenant_id, chain_hash, previous_hash, operation_type,
                input_ref_json, operation_token, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'diff',
                '{}'::jsonb, $3, 'created', $4
            )
            """,
            row_id,
            tenant_id,
            f"op_{uuid.uuid4().hex}",
            user_id,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE observability_runs SET status = 'completed' WHERE id = $1", row_id
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_run_token_diff_results(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        row_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO run_token_diff_results (
                id, tenant_id, chain_hash, previous_hash, base_run_id,
                compare_run_id, diff_summary_json, drift_flag, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), $3,
                $4, '{}'::jsonb, false, $5
            )
            """,
            row_id,
            tenant_id,
            uuid.uuid4(),
            uuid.uuid4(),
            user_id,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE run_token_diff_results SET drift_flag = true WHERE id = $1",
                row_id,
            )
    finally:
        await conn.close()


def test_append_only_registry_includes_all_observability_tables() -> None:
    expected_tables = {
        "observability_run_registry",
        "run_token_diff_definitions",
        "run_token_diff_results",
        "lineage_graph_snapshots",
        "governance_events",
        "run_performance_metrics",
        "observability_runs",
        "observability_results",
        "observability_evidence_links",
    }
    assert expected_tables.issubset(set(APPEND_ONLY_TABLES))

