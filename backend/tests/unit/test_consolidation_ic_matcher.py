from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from financeops.services.consolidation.ic_matcher import (
    IntercompanyToleranceConfig,
    MatchCandidateLine,
    match_intercompany_lines,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


def test_ic_matcher_tier1_and_tier2_and_unmatched_classifications() -> None:
    entity_a = _uuid("00000000-0000-0000-0000-000000000011")
    entity_b = _uuid("00000000-0000-0000-0000-000000000022")
    entity_c = _uuid("00000000-0000-0000-0000-000000000033")
    entity_d = _uuid("00000000-0000-0000-0000-000000000044")
    entity_e = _uuid("00000000-0000-0000-0000-000000000055")

    lines = [
        # Tier 1 matched (ic_reference + ordered pair + account_code)
        MatchCandidateLine(
            snapshot_line_id=_uuid("10000000-0000-0000-0000-000000000001"),
            entity_id=entity_a,
            account_code="IC-100",
            local_amount=Decimal("100.000000"),
            expected_rate=Decimal("1.200000"),
            parent_amount=Decimal("120.000000"),
            ic_reference="ICREF-1",
            ic_counterparty_entity=entity_b,
            transaction_date=date(2026, 3, 5),
            ic_account_class="IC_RECEIVABLE",
        ),
        MatchCandidateLine(
            snapshot_line_id=_uuid("10000000-0000-0000-0000-000000000002"),
            entity_id=entity_b,
            account_code="IC-100",
            local_amount=Decimal("-100.000000"),
            expected_rate=Decimal("1.200000"),
            parent_amount=Decimal("-120.000000"),
            ic_reference="ICREF-1",
            ic_counterparty_entity=entity_a,
            transaction_date=date(2026, 3, 6),
            ic_account_class="IC_PAYABLE",
        ),
        # Tier 2 timing_difference (counterparty + mirrored class, no ic_reference)
        MatchCandidateLine(
            snapshot_line_id=_uuid("20000000-0000-0000-0000-000000000001"),
            entity_id=entity_c,
            account_code="IC-200",
            local_amount=Decimal("100.000000"),
            expected_rate=Decimal("1.200000"),
            parent_amount=Decimal("120.000000"),
            ic_reference=None,
            ic_counterparty_entity=entity_d,
            transaction_date=date(2026, 3, 10),
            ic_account_class="IC_REVENUE",
        ),
        MatchCandidateLine(
            snapshot_line_id=_uuid("20000000-0000-0000-0000-000000000002"),
            entity_id=entity_d,
            account_code="IC-200",
            local_amount=Decimal("-100.000000"),
            expected_rate=Decimal("1.200000"),
            parent_amount=Decimal("-118.000000"),
            ic_reference=None,
            ic_counterparty_entity=entity_c,
            transaction_date=date(2026, 3, 12),
            ic_account_class="IC_EXPENSE",
        ),
        # Unmatched IC line => explicit unexplained pair.
        MatchCandidateLine(
            snapshot_line_id=_uuid("30000000-0000-0000-0000-000000000001"),
            entity_id=entity_e,
            account_code="IC-300",
            local_amount=Decimal("100.000000"),
            expected_rate=Decimal("1.000000"),
            parent_amount=Decimal("130.000000"),
            ic_reference="ICREF-UNMATCHED",
            ic_counterparty_entity=entity_a,
            transaction_date=None,
            ic_account_class="IC_RECEIVABLE",
        ),
    ]
    tolerance = IntercompanyToleranceConfig(
        amount_tolerance_parent=Decimal("0.010000"),
        fx_explained_tolerance_parent=Decimal("1.000000"),
        timing_tolerance_days=3,
    )

    decisions = match_intercompany_lines(lines=lines, tolerance=tolerance)
    classes = sorted(row.classification for row in decisions)
    assert classes == ["matched", "timing_difference", "unexplained"]

    tier1 = next(row for row in decisions if row.account_code == "IC-100")
    assert tier1.classification == "matched"
    tier2 = next(row for row in decisions if row.account_code == "IC-200")
    assert tier2.classification == "timing_difference"
    unmatched = next(row for row in decisions if row.account_code == "IC-300")
    assert unmatched.classification == "unexplained"
