from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from financeops.core.exceptions import ValidationError
from financeops.db.models.accounting_jv import EntryType, JVStatus
from financeops.modules.accounting_layer.application.journal_service import (
    _assert_balanced_active_lines,
    _is_posted_status,
    _map_journal_status,
)


class TestJournalStatusMapping:
    def test_draft_maps_to_draft(self) -> None:
        assert _map_journal_status(JVStatus.DRAFT, is_posted=False) == "DRAFT"

    def test_review_status_maps_to_review(self) -> None:
        assert _map_journal_status(JVStatus.PENDING_REVIEW, is_posted=False) == "REVIEWED"

    def test_approved_maps_to_approved(self) -> None:
        assert _map_journal_status(JVStatus.APPROVED, is_posted=False) == "APPROVED"

    def test_posted_flag_wins(self) -> None:
        assert _map_journal_status(JVStatus.APPROVED, is_posted=True) == "POSTED"

    def test_posted_status_helper(self) -> None:
        assert _is_posted_status(JVStatus.PUSHED) is True
        assert _is_posted_status(JVStatus.PUSH_IN_PROGRESS) is True
        assert _is_posted_status(JVStatus.APPROVED) is False


@pytest.mark.asyncio
async def test_balanced_active_lines_required() -> None:
    jv = SimpleNamespace(
        version=1,
        lines=[
            SimpleNamespace(
                jv_version=1,
                line_number=1,
                entry_type=EntryType.DEBIT,
                amount=Decimal("100.00"),
                base_amount=None,
            ),
            SimpleNamespace(
                jv_version=1,
                line_number=2,
                entry_type=EntryType.CREDIT,
                amount=Decimal("90.00"),
                base_amount=None,
            ),
        ],
    )
    with pytest.raises(ValidationError, match="imbalance"):
        await _assert_balanced_active_lines(jv)  # type: ignore[arg-type]
