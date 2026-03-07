from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from financeops.schemas.accounting_common import DrillResponseBase


def test_drill_response_base_normalizes_child_ids_deterministically() -> None:
    first = UUID("00000000-0000-0000-0000-000000000002")
    second = UUID("00000000-0000-0000-0000-000000000001")

    payload = DrillResponseBase(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        parent_reference_id=None,
        source_reference_id=UUID("00000000-0000-0000-0000-000000000011"),
        correlation_id=UUID("00000000-0000-0000-0000-000000000012"),
        child_ids=[first, second, first],
        metadata={"path": "ok"},
    )

    assert payload.child_ids == [second, first]


def test_drill_response_base_requires_correlation_id_uuid() -> None:
    with pytest.raises(ValidationError):
        DrillResponseBase(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            parent_reference_id=None,
            source_reference_id=None,
            correlation_id="not-a-uuid",
            child_ids=[],
            metadata={},
        )
