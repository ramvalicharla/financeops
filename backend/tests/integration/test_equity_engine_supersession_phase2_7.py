from __future__ import annotations

import uuid

import asyncpg
import pytest


async def _insert_statement(
    conn: asyncpg.Connection,
    *,
    row_id: uuid.UUID,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    statement_code: str,
    version_token: str,
    status: str,
    supersedes_id: uuid.UUID | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO equity_statement_definitions (
            id, tenant_id, chain_hash, previous_hash, organisation_id,
            statement_code, statement_name, reporting_currency_basis,
            ownership_basis_flag, version_token, effective_from,
            supersedes_id, status, created_by
        ) VALUES (
            $1, $2, repeat('a',64), repeat('b',64), $3,
            $4, 'EQ', 'source_currency',
            false, $5, DATE '2026-01-01',
            $6, $7, $8
        )
        """,
        row_id,
        tenant_id,
        organisation_id,
        statement_code,
        version_token,
        supersedes_id,
        status,
        uuid.uuid4(),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_allows_valid_linear_supersession(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        root = uuid.uuid4()
        child = uuid.uuid4()
        await _insert_statement(
            conn,
            row_id=root,
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_MAIN",
            version_token="v1",
            status="superseded",
            supersedes_id=None,
        )
        await _insert_statement(
            conn,
            row_id=child,
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_MAIN",
            version_token="v2",
            status="active",
            supersedes_id=root,
        )
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM equity_statement_definitions
            WHERE tenant_id = $1 AND organisation_id = $2 AND statement_code = 'EQ_MAIN'
            """,
            tenant_id,
            org_id,
        )
        assert count == 2
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_rejects_self_supersession(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        row_id = uuid.uuid4()
        with pytest.raises(asyncpg.exceptions.RaiseError, match="self-supersession"):
            await _insert_statement(
                conn,
                row_id=row_id,
                tenant_id=tenant_id,
                organisation_id=org_id,
                statement_code="EQ_MAIN",
                version_token="v1",
                status="active",
                supersedes_id=row_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_rejects_cross_family_supersession(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        first = uuid.uuid4()
        await _insert_statement(
            conn,
            row_id=first,
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_A",
            version_token="v1",
            status="active",
            supersedes_id=None,
        )
        with pytest.raises(asyncpg.exceptions.RaiseError, match="different families"):
            await _insert_statement(
                conn,
                row_id=uuid.uuid4(),
                tenant_id=tenant_id,
                organisation_id=org_id,
                statement_code="EQ_B",
                version_token="v1",
                status="candidate",
                supersedes_id=first,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_rejects_branching_supersession(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        parent = uuid.uuid4()
        await _insert_statement(
            conn,
            row_id=parent,
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_MAIN",
            version_token="v1",
            status="superseded",
            supersedes_id=None,
        )
        await _insert_statement(
            conn,
            row_id=uuid.uuid4(),
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_MAIN",
            version_token="v2",
            status="candidate",
            supersedes_id=parent,
        )
        with pytest.raises(asyncpg.exceptions.RaiseError, match="branching"):
            await _insert_statement(
                conn,
                row_id=uuid.uuid4(),
                tenant_id=tenant_id,
                organisation_id=org_id,
                statement_code="EQ_MAIN",
                version_token="v3",
                status="candidate",
                supersedes_id=parent,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_statement_rejects_second_active_version_for_same_code(
    equity_phase2_7_db_url: str,
) -> None:
    conn = await asyncpg.connect(equity_phase2_7_db_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tenant_id = uuid.uuid4()
        org_id = uuid.uuid4()
        await _insert_statement(
            conn,
            row_id=uuid.uuid4(),
            tenant_id=tenant_id,
            organisation_id=org_id,
            statement_code="EQ_MAIN",
            version_token="v1",
            status="active",
            supersedes_id=None,
        )
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await _insert_statement(
                conn,
                row_id=uuid.uuid4(),
                tenant_id=tenant_id,
                organisation_id=org_id,
                statement_code="EQ_MAIN",
                version_token="v2",
                status="active",
                supersedes_id=None,
            )
    finally:
        await conn.close()
