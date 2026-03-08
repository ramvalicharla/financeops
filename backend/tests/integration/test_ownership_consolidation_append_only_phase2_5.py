from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest

from financeops.db.append_only import APPEND_ONLY_TABLES


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_ownership_structure_definitions(
    ownership_phase2_5_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        definition_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO ownership_structure_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                ownership_structure_code, ownership_structure_name, hierarchy_scope_ref,
                ownership_basis_type, version_token, effective_from, status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            definition_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            tenant_id,
            "grp_owner_1",
            "Group Ownership",
            "scope-main",
            "equity_percentage",
            "tok_struct_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE ownership_structure_definitions SET ownership_structure_name = $1 WHERE id = $2",
                "Changed",
                definition_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_ownership_consolidation_runs(
    ownership_phase2_5_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        run_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO ownership_consolidation_runs (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_period, hierarchy_version_token, scope_version_token,
                ownership_structure_version_token, ownership_rule_version_token,
                minority_interest_rule_version_token, source_consolidation_run_refs_json,
                run_token, run_status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13,$14,$15)
            """,
            run_id,
            tenant_id,
            "b" * 64,
            "0" * 64,
            tenant_id,
            date(2026, 1, 31),
            "h_v1",
            "s_v1",
            "own_struct_v1",
            "own_rule_v1",
            "minority_v1",
            '[{"source_type":"consolidation_run","run_id":"00000000-0000-0000-0000-000000000001"}]',
            "run_tok_1",
            "created",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE ownership_consolidation_runs SET run_status = $1 WHERE id = $2",
                "failed",
                run_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ownership_relationships_reject_cycle(
    ownership_phase2_5_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    created_by = uuid.uuid4()
    parent_a = uuid.uuid4()
    child_b = uuid.uuid4()
    child_c = uuid.uuid4()
    conn = await asyncpg.connect(
        ownership_phase2_5_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        struct_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO ownership_structure_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                ownership_structure_code, ownership_structure_name, hierarchy_scope_ref,
                ownership_basis_type, version_token, effective_from, status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            struct_id,
            tenant_id,
            "c" * 64,
            "0" * 64,
            org_id,
            "grp_owner_cycle",
            "Cycle Check",
            "scope-main",
            "equity_percentage",
            "tok_struct_cycle",
            date(2026, 1, 1),
            "active",
            created_by,
        )
        await conn.execute(
            """
            INSERT INTO ownership_relationships (
                id, tenant_id, chain_hash, previous_hash, organisation_id, ownership_structure_id,
                parent_entity_id, child_entity_id, ownership_percentage, control_indicator,
                minority_interest_indicator, proportionate_consolidation_indicator, effective_from,
                status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            """,
            uuid.uuid4(),
            tenant_id,
            "d" * 64,
            "0" * 64,
            org_id,
            struct_id,
            parent_a,
            child_b,
            80,
            True,
            False,
            False,
            date(2026, 1, 1),
            "active",
            created_by,
        )
        await conn.execute(
            """
            INSERT INTO ownership_relationships (
                id, tenant_id, chain_hash, previous_hash, organisation_id, ownership_structure_id,
                parent_entity_id, child_entity_id, ownership_percentage, control_indicator,
                minority_interest_indicator, proportionate_consolidation_indicator, effective_from,
                status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            """,
            uuid.uuid4(),
            tenant_id,
            "e" * 64,
            "0" * 64,
            org_id,
            struct_id,
            child_b,
            child_c,
            70,
            True,
            False,
            False,
            date(2026, 1, 1),
            "active",
            created_by,
        )
        with pytest.raises(asyncpg.PostgresError, match="cycle"):
            await conn.execute(
                """
                INSERT INTO ownership_relationships (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, ownership_structure_id,
                    parent_entity_id, child_entity_id, ownership_percentage, control_indicator,
                    minority_interest_indicator, proportionate_consolidation_indicator, effective_from,
                    status, created_by
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                """,
                uuid.uuid4(),
                tenant_id,
                "f" * 64,
                "0" * 64,
                org_id,
                struct_id,
                child_c,
                parent_a,
                60,
                True,
                False,
                False,
                date(2026, 1, 1),
                "active",
                created_by,
            )
    finally:
        await conn.close()


def test_append_only_registry_includes_ownership_tables() -> None:
    required = {
        "ownership_structure_definitions",
        "ownership_relationships",
        "ownership_consolidation_rule_definitions",
        "minority_interest_rule_definitions",
        "ownership_consolidation_runs",
        "ownership_consolidation_metric_results",
        "ownership_consolidation_variance_results",
        "ownership_consolidation_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
