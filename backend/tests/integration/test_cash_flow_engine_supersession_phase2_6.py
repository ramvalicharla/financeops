from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import asyncpg
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_statement_definition_allows_linear_supersession(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    created_by = uuid.uuid4()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
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
            first_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "CF_CHAIN",
            "Cash Flow Chain v1",
            "indirect",
            "{}",
            "tok_v1",
            date(2026, 1, 1),
            "candidate",
            created_by,
        )
        await conn.execute(
            """
            INSERT INTO cash_flow_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                definition_name, method_type, layout_json, version_token, effective_from, supersedes_id, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14)
            """,
            second_id,
            tenant_id,
            "b" * 64,
            "0" * 64,
            org_id,
            "CF_CHAIN",
            "Cash Flow Chain v2",
            "indirect",
            "{}",
            "tok_v2",
            date(2026, 2, 1),
            first_id,
            "candidate",
            created_by,
        )
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM cash_flow_statement_definitions
            WHERE definition_code='CF_CHAIN' AND tenant_id=$1
            """,
            tenant_id,
        )
        assert count == 2
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_statement_definition_rejects_self_supersession(
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
        with pytest.raises(asyncpg.PostgresError, match="self-supersession"):
            await conn.execute(
                """
                INSERT INTO cash_flow_statement_definitions (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                    definition_name, method_type, layout_json, version_token, effective_from, supersedes_id, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14)
                """,
                row_id,
                tenant_id,
                "a" * 64,
                "0" * 64,
                org_id,
                "CF_SELF",
                "Self",
                "indirect",
                "{}",
                "tok_self",
                date(2026, 1, 1),
                row_id,
                "candidate",
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_statement_definition_rejects_cross_code_supersession(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    first_id = uuid.uuid4()
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
            first_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "CF_A",
            "A",
            "indirect",
            "{}",
            "tok_a1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="different codes"):
            await conn.execute(
                """
                INSERT INTO cash_flow_statement_definitions (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                    definition_name, method_type, layout_json, version_token, effective_from, supersedes_id, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14)
                """,
                uuid.uuid4(),
                tenant_id,
                "b" * 64,
                "0" * 64,
                org_id,
                "CF_B",
                "B",
                "indirect",
                "{}",
                "tok_b1",
                date(2026, 2, 1),
                first_id,
                "candidate",
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_statement_definition_rejects_branching_supersession(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    base_id = uuid.uuid4()
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
            base_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "CF_BRANCH",
            "Base",
            "indirect",
            "{}",
            "tok_base",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute(
            """
            INSERT INTO cash_flow_statement_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                definition_name, method_type, layout_json, version_token, effective_from, supersedes_id, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14)
            """,
            uuid.uuid4(),
            tenant_id,
            "b" * 64,
            "0" * 64,
            org_id,
            "CF_BRANCH",
            "Child1",
            "indirect",
            "{}",
            "tok_child_1",
            date(2026, 2, 1),
            base_id,
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="branching"):
            await conn.execute(
                """
                INSERT INTO cash_flow_statement_definitions (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                    definition_name, method_type, layout_json, version_token, effective_from, supersedes_id, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13,$14)
                """,
                uuid.uuid4(),
                tenant_id,
                "c" * 64,
                "0" * 64,
                org_id,
                "CF_BRANCH",
                "Child2",
                "indirect",
                "{}",
                "tok_child_2",
                date(2026, 3, 1),
                base_id,
                "candidate",
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_line_mapping_rejects_self_supersession(
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
        with pytest.raises(asyncpg.PostgresError, match="self-supersession"):
            await conn.execute(
                """
                INSERT INTO cash_flow_line_mappings (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, mapping_code, line_code,
                    line_name, section_code, line_order, method_type, source_metric_code, sign_multiplier,
                    aggregation_type, ownership_applicability, fx_applicability, version_token, effective_from,
                    supersedes_id, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                """,
                row_id,
                tenant_id,
                "a" * 64,
                "0" * 64,
                org_id,
                "MAP_SELF",
                "L1",
                "Line 1",
                "operating",
                1,
                "indirect",
                "revenue",
                Decimal("1.000000"),
                "sum",
                "any",
                "any",
                "tok_map_self",
                date(2026, 1, 1),
                row_id,
                "candidate",
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_statement_definition_rejects_second_active_version_for_same_code(
    cash_flow_phase2_6_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
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
            uuid.uuid4(),
            tenant_id,
            "a" * 64,
            "0" * 64,
            org_id,
            "CF_ACTIVE",
            "Active 1",
            "indirect",
            "{}",
            "tok_active_1",
            date(2026, 1, 1),
            "active",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO cash_flow_statement_definitions (
                    id, tenant_id, chain_hash, previous_hash, organisation_id, definition_code,
                    definition_name, method_type, layout_json, version_token, effective_from, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13)
                """,
                uuid.uuid4(),
                tenant_id,
                "b" * 64,
                "0" * 64,
                org_id,
                "CF_ACTIVE",
                "Active 2",
                "indirect",
                "{}",
                "tok_active_2",
                date(2026, 2, 1),
                "active",
                uuid.uuid4(),
            )
    finally:
        await conn.close()
