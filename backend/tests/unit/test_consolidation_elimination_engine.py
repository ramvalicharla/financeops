from __future__ import annotations

import uuid
from decimal import Decimal

from financeops.services.consolidation.elimination_engine import build_elimination_decisions
from financeops.services.consolidation.ic_matcher import IntercompanyMatchDecision


def _pair(classification: str, match_key_hash: str) -> IntercompanyMatchDecision:
    return IntercompanyMatchDecision(
        match_key_hash=match_key_hash,
        entity_from=uuid.uuid4(),
        entity_to=uuid.uuid4(),
        account_code="IC-100",
        ic_reference="ICREF-1",
        amount_local_from=Decimal("100.000000"),
        amount_local_to=Decimal("-100.000000"),
        amount_parent_from=Decimal("120.000000"),
        amount_parent_to=Decimal("-119.500000"),
        expected_difference=Decimal("0.000000"),
        actual_difference=Decimal("0.500000"),
        fx_explained=Decimal("0.500000"),
        unexplained_difference=Decimal("0.000000"),
        classification=classification,
        transaction_date_from=None,
        transaction_date_to=None,
    )


def test_elimination_applies_for_matched_and_fx_explained_and_blocks_others() -> None:
    pairs = [
        _pair("matched", "a"),
        _pair("fx_explained", "b"),
        _pair("timing_difference", "c"),
        _pair("unexplained", "d"),
    ]
    pair_ids = {pair.match_key_hash: uuid.uuid4() for pair in pairs}

    decisions = build_elimination_decisions(pair_ids=pair_ids, pairs=pairs)

    status_by_class = {row.classification_at_time: row.elimination_status for row in decisions}
    assert status_by_class == {
        "matched": "applied",
        "fx_explained": "applied",
        "timing_difference": "blocked",
        "unexplained": "blocked",
    }
    fx_row = next(row for row in decisions if row.classification_at_time == "fx_explained")
    assert fx_row.fx_component_impact_parent == Decimal("0.500000")
    blocked_row = next(row for row in decisions if row.classification_at_time == "timing_difference")
    assert blocked_row.eliminated_amount_parent == Decimal("0.000000")
