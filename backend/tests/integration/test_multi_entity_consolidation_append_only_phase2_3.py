from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_entity_hierarchies(
    multi_entity_phase2_3_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        multi_entity_phase2_3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        hierarchy_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO entity_hierarchies (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                hierarchy_code, hierarchy_name, hierarchy_type, version_token,
                effective_from, status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            hierarchy_id,
            tenant_id,
            "c" * 64,
            "0" * 64,
            tenant_id,
            "grp_main",
            "Group Main",
            "legal",
            "tok_h1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE entity_hierarchies SET hierarchy_name = $1 WHERE id = $2",
                "Changed",
                hierarchy_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_entity_hierarchy_nodes_reject_self_parent(
    multi_entity_phase2_3_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        multi_entity_phase2_3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        hierarchy_id = uuid.uuid4()
        created_by = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO entity_hierarchies (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                hierarchy_code, hierarchy_name, hierarchy_type, version_token,
                effective_from, status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            hierarchy_id,
            tenant_id,
            "d" * 64,
            "0" * 64,
            tenant_id,
            "grp_main_2",
            "Group Main 2",
            "legal",
            "tok_h2",
            date(2026, 1, 1),
            "candidate",
            created_by,
        )
        node_id = uuid.uuid4()
        with pytest.raises(asyncpg.PostgresError, match="own parent"):
            await conn.execute(
                """
                INSERT INTO entity_hierarchy_nodes (
                    id, tenant_id, chain_hash, previous_hash, hierarchy_id, entity_id,
                    parent_node_id, node_level, effective_from, status, created_by
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                node_id,
                tenant_id,
                "e" * 64,
                "0" * 64,
                hierarchy_id,
                uuid.uuid4(),
                node_id,
                0,
                date(2026, 1, 1),
                "candidate",
                created_by,
            )
    finally:
        await conn.close()

