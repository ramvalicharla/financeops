from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_diff_definition_allows_valid_linear_supersession(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'intra_module',
                '[]'::jsonb, 'obs_v1', $3, NULL, 'active', $4
            )
            """,
            parent_id,
            tenant_id,
            date(2026, 1, 1),
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('c', 64), repeat('d', 64), 'intra_module',
                '[]'::jsonb, 'obs_v2', $3, $4, 'candidate', $5
            )
            """,
            child_id,
            tenant_id,
            date(2026, 2, 1),
            parent_id,
            user_id,
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_diff_definition_rejects_self_supersession(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        row_id = uuid.uuid4()
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO run_token_diff_definitions (
                    id, tenant_id, chain_hash, previous_hash, comparison_type,
                    allowed_modules_json, version_token, effective_from,
                    supersedes_id, status, created_by
                ) VALUES (
                    $1, $2, repeat('a', 64), repeat('b', 64), 'cross_module',
                    '[]'::jsonb, 'self_v1', $3, $1, 'candidate', $4
                )
                """,
                row_id,
                uuid.uuid4(),
                date(2026, 1, 1),
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_diff_definition_rejects_cross_type_supersession(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'intra_module',
                '[]'::jsonb, 'cross_parent', $3, NULL, 'candidate', $4
            )
            """,
            parent_id,
            tenant_id,
            date(2026, 1, 1),
            user_id,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO run_token_diff_definitions (
                    id, tenant_id, chain_hash, previous_hash, comparison_type,
                    allowed_modules_json, version_token, effective_from,
                    supersedes_id, status, created_by
                ) VALUES (
                    $1, $2, repeat('c', 64), repeat('d', 64), 'cross_period',
                    '[]'::jsonb, 'cross_child', $3, $4, 'candidate', $5
                )
                """,
                uuid.uuid4(),
                tenant_id,
                date(2026, 2, 1),
                parent_id,
                user_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_diff_definition_rejects_branching_supersession(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'cross_module',
                '[]'::jsonb, 'branch_parent', $3, NULL, 'candidate', $4
            )
            """,
            parent_id,
            tenant_id,
            date(2026, 1, 1),
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('c', 64), repeat('d', 64), 'cross_module',
                '[]'::jsonb, 'branch_child_a', $3, $4, 'candidate', $5
            )
            """,
            uuid.uuid4(),
            tenant_id,
            date(2026, 2, 1),
            parent_id,
            user_id,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO run_token_diff_definitions (
                    id, tenant_id, chain_hash, previous_hash, comparison_type,
                    allowed_modules_json, version_token, effective_from,
                    supersedes_id, status, created_by
                ) VALUES (
                    $1, $2, repeat('e', 64), repeat('f', 64), 'cross_module',
                    '[]'::jsonb, 'branch_child_b', $3, $4, 'candidate', $5
                )
                """,
                uuid.uuid4(),
                tenant_id,
                date(2026, 3, 1),
                parent_id,
                user_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_diff_definition_rejects_second_active_version_for_same_type(
    observability_phase3_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        observability_phase3_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO run_token_diff_definitions (
                id, tenant_id, chain_hash, previous_hash, comparison_type,
                allowed_modules_json, version_token, effective_from,
                supersedes_id, status, created_by
            ) VALUES (
                $1, $2, repeat('a', 64), repeat('b', 64), 'cross_period',
                '[]'::jsonb, 'active_1', $3, NULL, 'active', $4
            )
            """,
            uuid.uuid4(),
            tenant_id,
            date(2026, 1, 1),
            user_id,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO run_token_diff_definitions (
                    id, tenant_id, chain_hash, previous_hash, comparison_type,
                    allowed_modules_json, version_token, effective_from,
                    supersedes_id, status, created_by
                ) VALUES (
                    $1, $2, repeat('c', 64), repeat('d', 64), 'cross_period',
                    '[]'::jsonb, 'active_2', $3, NULL, 'active', $4
                )
                """,
                uuid.uuid4(),
                tenant_id,
                date(2026, 2, 1),
                user_id,
            )
    finally:
        await conn.close()

