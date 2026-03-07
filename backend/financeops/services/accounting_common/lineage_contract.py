from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID


@dataclass(frozen=True)
class LineageMetadata:
    parent_reference_id: UUID | None
    source_reference_id: UUID | None
    correlation_id: UUID
    tenant_id: UUID
    created_at: datetime


def build_lineage_metadata(
    *,
    parent_reference_id: UUID | None,
    source_reference_id: UUID | None,
    correlation_id: UUID,
    tenant_id: UUID,
    created_at: datetime,
) -> LineageMetadata:
    return LineageMetadata(
        parent_reference_id=parent_reference_id,
        source_reference_id=source_reference_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        created_at=created_at,
    )


def validate_lineage_chain(chain: Sequence[LineageMetadata]) -> bool:
    if not chain:
        return False

    first = chain[0]
    if first.source_reference_id is None:
        return False

    for item in chain:
        if item.correlation_id != first.correlation_id:
            return False
        if item.tenant_id != first.tenant_id:
            return False

    for idx in range(1, len(chain)):
        previous = chain[idx - 1]
        current = chain[idx]
        if current.parent_reference_id is None:
            return False
        if previous.source_reference_id is None:
            return False
        if current.parent_reference_id != previous.source_reference_id:
            return False

    return True
