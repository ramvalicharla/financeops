from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from financeops.db.models.audit import AuditTrail
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.services.audit_service import log_action, verify_tenant_chain
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _insert_audit_record(
    session_factory,
    tenant_id: uuid.UUID,
    idx: int,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        async with session_factory() as session:
            await set_tenant_context(session, tenant_id)
            try:
                await log_action(
                    session,
                    tenant_id=tenant_id,
                    user_id=None,
                    action=f"action_{idx}",
                    resource_type="concurrency_test",
                )
                await session.commit()
            finally:
                await clear_tenant_context(session)


@pytest.mark.asyncio
async def test_concurrent_inserts_no_chain_fork(engine) -> None:
    """20 concurrent inserts produce a valid, unforked chain."""
    tenant_id = uuid.uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    semaphore = asyncio.Semaphore(10)

    await asyncio.gather(
        *[
            _insert_audit_record(session_factory, tenant_id, i, semaphore)
            for i in range(20)
        ]
    )

    async with session_factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(AuditTrail)
            .where(AuditTrail.tenant_id == tenant_id)
        )
        records = list(result.scalars().all())

    assert len(records) == 20

    by_prev: dict[str, list[AuditTrail]] = {}
    for record in records:
        by_prev.setdefault(record.previous_hash, []).append(record)

    for previous_hash, children in by_prev.items():
        assert len(children) == 1, f"Chain forked at previous_hash={previous_hash}"

    current_prev = GENESIS_HASH
    visited: set[uuid.UUID] = set()
    for _ in range(len(records)):
        next_nodes = by_prev.get(current_prev, [])
        assert len(next_nodes) == 1
        node = next_nodes[0]
        expected = compute_chain_hash(
            {
                "tenant_id": str(node.tenant_id),
                "user_id": str(node.user_id) if node.user_id else None,
                "action": node.action,
                "resource_type": node.resource_type,
                "resource_id": node.resource_id,
                "resource_name": node.resource_name,
                "old_value_hash": node.old_value_hash,
                "new_value_hash": node.new_value_hash,
                "ip_address": node.ip_address,
            },
            current_prev,
        )
        assert node.chain_hash == expected
        visited.add(node.id)
        current_prev = node.chain_hash

    assert len(visited) == len(records)


@pytest.mark.asyncio
async def test_verify_chain_passes_after_concurrent_writes(engine) -> None:
    """verify_chain() confirms integrity after 50 concurrent writes."""
    tenant_id = uuid.uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    semaphore = asyncio.Semaphore(10)

    await asyncio.gather(
        *[
            _insert_audit_record(session_factory, tenant_id, i, semaphore)
            for i in range(50)
        ]
    )

    async with session_factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await verify_tenant_chain(session, tenant_id)

    assert result.is_valid is True
    assert result.total_records == 50


@pytest.mark.asyncio
async def test_different_tenants_do_not_share_lock(engine) -> None:
    """Two tenants can write concurrently without blocking each other."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    semaphore = asyncio.Semaphore(10)

    tasks = [
        *[_insert_audit_record(session_factory, tenant_a, i, semaphore) for i in range(10)],
        *[_insert_audit_record(session_factory, tenant_b, i, semaphore) for i in range(10)],
    ]
    await asyncio.gather(*tasks)

    async with session_factory() as session:
        await set_tenant_context(session, tenant_a)
        chain_a = await verify_tenant_chain(session, tenant_a)
        await clear_tenant_context(session)

        await set_tenant_context(session, tenant_b)
        chain_b = await verify_tenant_chain(session, tenant_b)

        count_a = await session.scalar(
            select(func.count())
            .select_from(AuditTrail)
            .where(AuditTrail.tenant_id == tenant_a)
        )
        count_b = await session.scalar(
            select(func.count())
            .select_from(AuditTrail)
            .where(AuditTrail.tenant_id == tenant_b)
        )

    assert chain_a.is_valid is True
    assert chain_b.is_valid is True
    assert count_a == 10
    assert count_b == 10
