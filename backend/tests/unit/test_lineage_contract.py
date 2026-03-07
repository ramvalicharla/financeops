from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from financeops.services.accounting_common.lineage_contract import (
    build_lineage_metadata,
    validate_lineage_chain,
)


def _uuid(raw: str) -> UUID:
    return UUID(raw)


def test_lineage_metadata_builder_and_chain_validation() -> None:
    correlation_id = _uuid("00000000-0000-0000-0000-00000000abcd")
    tenant_id = _uuid("00000000-0000-0000-0000-00000000aaaa")
    root_source = _uuid("00000000-0000-0000-0000-00000000aa01")
    child_source = _uuid("00000000-0000-0000-0000-00000000aa02")

    root = build_lineage_metadata(
        parent_reference_id=None,
        source_reference_id=root_source,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
    )
    child = build_lineage_metadata(
        parent_reference_id=root_source,
        source_reference_id=child_source,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
    )

    assert validate_lineage_chain([root, child]) is True


def test_lineage_chain_fails_when_tenant_or_parent_mismatch() -> None:
    correlation_id = _uuid("00000000-0000-0000-0000-00000000abce")
    root_source = _uuid("00000000-0000-0000-0000-00000000aa11")

    root = build_lineage_metadata(
        parent_reference_id=None,
        source_reference_id=root_source,
        correlation_id=correlation_id,
        tenant_id=_uuid("00000000-0000-0000-0000-00000000bbbb"),
        created_at=datetime.now(timezone.utc),
    )
    bad_child = build_lineage_metadata(
        parent_reference_id=_uuid("00000000-0000-0000-0000-00000000dead"),
        source_reference_id=_uuid("00000000-0000-0000-0000-00000000aa12"),
        correlation_id=correlation_id,
        tenant_id=_uuid("00000000-0000-0000-0000-00000000cccc"),
        created_at=datetime.now(timezone.utc),
    )

    assert validate_lineage_chain([root, bad_child]) is False
