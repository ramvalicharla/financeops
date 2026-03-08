from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest

from financeops.db.append_only import APPEND_ONLY_TABLES


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_cash_flow_statement_definitions(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    row_id = uuid.uuid4()
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        await conn.execute(
            """
            INSERT INTO cash_flow_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                definition_name, method_type, layout_json, version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13)
            """,
            row_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "CF_MAIN",
            "Cash Flow Main",
            "indirect",
            "{}",
            "tok_stmt_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE cash_flow_statement_definitions SET definition_name = $1 WHERE id = $2",
                "Renamed",
                row_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_cash_flow_runs(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    conn = await asyncpg.connect(
        cash_flow_phase2_6_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        hierarchy_id = uuid.uuid4()
        scope_id = uuid.uuid4()
        consolidation_run_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO entity_hierarchies (
                id, tenant_id, chain_hash, previous_hash, organisation_id, hierarchy_code,
                hierarchy_name, hierarchy_type, version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            hierarchy_id,
            tenant_id,
            "h" * 64,
            "0" * 64,
            org_id,
            "H_CF",
            "Hierarchy",
            "legal",
            "h_tok",
            date(2026, 1, 1),
            "active",
            uuid.uuid4(),
        )
        await conn.execute(
            """
            INSERT INTO consolidation_scopes (
                id, tenant_id, chain_hash, previous_hash, organisation_id, scope_code,
                scope_name, hierarchy_id, scope_selector_json, version_token, effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13)
            """,
            scope_id,
            tenant_id,
            "s" * 64,
            "0" * 64,
            org_id,
            "S_CF",
            "Scope",
            hierarchy_id,
            "{}",
            "s_tok",
            date(2026, 1, 1),
            "active",
            uuid.uuid4(),
        )
        await conn.execute(
            """
            INSERT INTO multi_entity_consolidation_runs (
                id, tenant_id, chain_hash, previous_hash, organisation_id, reporting_period,
                hierarchy_id, scope_id, hierarchy_version_token, scope_version_token, rule_version_token,
                intercompany_version_token, adjustment_version_token, source_run_refs_json, run_token, run_status,
                validation_summary_json, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,$15,$16,$17::jsonb,$18)
            """,
            consolidation_run_id,
            tenant_id,
            "r" * 64,
            "0" * 64,
            org_id,
            date(2026, 1, 31),
            hierarchy_id,
            scope_id,
            "h_v1",
            "s_v1",
            "r_v1",
            "i_v1",
            "a_v1",
            '[{"source_type":"metric_run","run_id":"00000000-0000-0000-0000-000000000001"}]',
            "run_src",
            "completed",
            "{}",
            uuid.uuid4(),
        )
        run_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO cash_flow_runs (
                id, tenant_id, chain_hash, previous_hash, organisation_id, reporting_period,
                statement_definition_version_token, line_mapping_version_token, bridge_rule_version_token,
                source_consolidation_run_ref, source_fx_translation_run_ref_nullable,
                source_ownership_consolidation_run_ref_nullable, run_token, run_status,
                validation_summary_json, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16)
            """,
            run_id,
            tenant_id,
            "c" * 64,
            "0" * 64,
            org_id,
            date(2026, 1, 31),
            "stmt_v1",
            "map_v1",
            "bridge_v1",
            consolidation_run_id,
            None,
            None,
            "cash_run_1",
            "created",
            "{}",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE cash_flow_runs SET run_status = $1 WHERE id = $2",
                "failed",
                run_id,
            )
    finally:
        await conn.close()


def test_append_only_registry_includes_cash_flow_tables() -> None:
    expected = {
        "cash_flow_statement_definitions",
        "cash_flow_line_mappings",
        "cash_flow_bridge_rule_definitions",
        "cash_flow_runs",
        "cash_flow_line_results",
        "cash_flow_evidence_links",
    }
    assert expected.issubset(set(APPEND_ONLY_TABLES))
