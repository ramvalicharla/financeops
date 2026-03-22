from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.utils.determinism import canonical_json_dumps

log = logging.getLogger(__name__)

GENESIS_HASH: str = "0" * 64


def compute_chain_hash(record_data: dict, previous_hash: str) -> str:
    """
    Compute the chain hash for a new record.
    Uses canonical_json_dumps() for deterministic serialization.
    SHA256 of: canonical_json(record_data) + previous_hash
    Returns: 64-char hex digest.
    """
    canonical = canonical_json_dumps(record_data)
    payload = canonical + previous_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ChainVerificationResult:
    is_valid: bool
    total_records: int
    first_broken_at: int | None  # 0-based index into records list


def verify_chain(records: list[dict]) -> ChainVerificationResult:
    """
    Verify chain integrity across a list of record dicts.
    Each record must have: chain_hash, previous_hash, and all other fields
    that were used to compute the chain_hash.

    The first record's previous_hash must be GENESIS_HASH.
    Each subsequent record's previous_hash must equal the prior record's chain_hash.
    The stored chain_hash must match recomputed hash.
    """
    if not records:
        return ChainVerificationResult(is_valid=True, total_records=0, first_broken_at=None)

    for i, record in enumerate(records):
        stored_chain_hash = record.get("chain_hash", "")
        stored_previous_hash = record.get("previous_hash", "")

        # Verify previous_hash linkage
        if i == 0:
            if stored_previous_hash != GENESIS_HASH:
                log.error("Chain broken at index 0: expected GENESIS_HASH as previous_hash")
                return ChainVerificationResult(
                    is_valid=False, total_records=len(records), first_broken_at=0
                )
        else:
            expected_previous = records[i - 1].get("chain_hash", "")
            if stored_previous_hash != expected_previous:
                log.error(
                    "Chain broken at index %d: previous_hash mismatch", i
                )
                return ChainVerificationResult(
                    is_valid=False, total_records=len(records), first_broken_at=i
                )

        # Recompute and verify chain_hash
        data_for_hash = {
            k: v for k, v in record.items()
            if k not in ("chain_hash", "previous_hash")
        }
        recomputed = compute_chain_hash(data_for_hash, stored_previous_hash)
        if recomputed != stored_chain_hash:
            log.error(
                "Chain hash mismatch at index %d: stored=%s recomputed=%s",
                i, stored_chain_hash[:8], recomputed[:8],
            )
            return ChainVerificationResult(
                is_valid=False, total_records=len(records), first_broken_at=i
            )

    return ChainVerificationResult(
        is_valid=True, total_records=len(records), first_broken_at=None
    )


async def get_previous_hash_locked(
    session: AsyncSession,
    model_class: type,
    tenant_id: UUID,
) -> str:
    """
    Acquire a transaction-scoped advisory lock for tenant+table, then
    return the most recent chain_hash for the model.
    Lock lifetime is tied to the current transaction.
    """
    lock_key = hashlib.md5(
        f"{model_class.__tablename__}:{tenant_id}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    lock_int = int(lock_key[:15], 16)

    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:k)"),
        {"k": lock_int},
    )

    result = await session.execute(
        sa.select(model_class.chain_hash)
        .where(model_class.tenant_id == tenant_id)
        .order_by(sa.desc(model_class.created_at))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return GENESIS_HASH
    return str(row)


async def get_previous_hash(
    session: AsyncSession,
    model_class: type,
    tenant_id: UUID,
) -> str:
    """
    Backward-compatible alias. Use get_previous_hash_locked directly.
    """
    return await get_previous_hash_locked(session, model_class, tenant_id)
