from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.audit import AuditTrail
from financeops.utils.chain_hash import (
    ChainVerificationResult,
    GENESIS_HASH,
    compute_chain_hash,
    get_previous_hash_locked,
    verify_chain,
)
from financeops.utils.determinism import sha256_hex_text, canonical_json_dumps

log = logging.getLogger(__name__)


async def log_action(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    resource_name: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditTrail:
    """
    Write an immutable audit trail entry with chain hash integrity.
    Never updates existing records — always inserts a new row.
    """
    old_value_hash = (
        sha256_hex_text(canonical_json_dumps(old_value)) if old_value is not None else None
    )
    new_value_hash = (
        sha256_hex_text(canonical_json_dumps(new_value)) if new_value is not None else None
    )

    previous_hash = await get_previous_hash_locked(session, AuditTrail, tenant_id)

    record_data = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id) if user_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "old_value_hash": old_value_hash,
        "new_value_hash": new_value_hash,
        "ip_address": ip_address,
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    entry = AuditTrail(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        old_value_hash=old_value_hash,
        new_value_hash=new_value_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(entry)
    await session.flush()
    log.debug(
        "Audit: action=%s resource=%s/%s tenant=%s",
        action,
        resource_type,
        resource_id,
        str(tenant_id)[:8],
    )
    return entry


async def verify_tenant_chain(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> ChainVerificationResult:
    """
    Load all audit records for a tenant ordered by created_at
    and verify the chain integrity.
    """
    result = await session.execute(
        select(AuditTrail).where(AuditTrail.tenant_id == tenant_id)
    )
    rows = result.scalars().all()
    if not rows:
        return ChainVerificationResult(is_valid=True, total_records=0, first_broken_at=None)

    by_previous_hash: dict[str, list[dict[str, str | None]]] = {}
    for row in rows:
        row_dict = {
            "tenant_id": str(row.tenant_id),
            "user_id": str(row.user_id) if row.user_id else None,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "resource_name": row.resource_name,
            "old_value_hash": row.old_value_hash,
            "new_value_hash": row.new_value_hash,
            "ip_address": row.ip_address,
            "chain_hash": row.chain_hash,
            "previous_hash": row.previous_hash,
        }
        by_previous_hash.setdefault(row.previous_hash, []).append(row_dict)

    ordered: list[dict[str, str | None]] = []
    current_previous_hash = GENESIS_HASH
    visited_hashes: set[str] = set()
    while len(ordered) < len(rows):
        next_nodes = by_previous_hash.get(current_previous_hash, [])
        if len(next_nodes) != 1:
            return ChainVerificationResult(
                is_valid=False,
                total_records=len(rows),
                first_broken_at=len(ordered),
            )
        node = next_nodes[0]
        node_hash = str(node["chain_hash"])
        if node_hash in visited_hashes:
            return ChainVerificationResult(
                is_valid=False,
                total_records=len(rows),
                first_broken_at=len(ordered),
            )
        visited_hashes.add(node_hash)
        ordered.append(node)
        current_previous_hash = node_hash

    return verify_chain(ordered)


async def get_audit_trail(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditTrail]:
    """Retrieve audit trail records for a tenant with optional filtering."""
    query = (
        select(AuditTrail)
        .where(AuditTrail.tenant_id == tenant_id)
        .order_by(desc(AuditTrail.created_at))
        .limit(limit)
        .offset(offset)
    )
    if resource_type:
        query = query.where(AuditTrail.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditTrail.resource_id == resource_id)
    result = await session.execute(query)
    return list(result.scalars().all())

