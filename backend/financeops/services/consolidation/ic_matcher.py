from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount
from financeops.services.fx.variance import compute_fx_variance
from financeops.utils.determinism import sha256_hex_text

MIRRORED_IC_ACCOUNT_CLASS: dict[str, str] = {
    "IC_RECEIVABLE": "IC_PAYABLE",
    "IC_PAYABLE": "IC_RECEIVABLE",
    "IC_REVENUE": "IC_EXPENSE",
    "IC_EXPENSE": "IC_REVENUE",
}


@dataclass(frozen=True)
class IntercompanyToleranceConfig:
    amount_tolerance_parent: Decimal
    fx_explained_tolerance_parent: Decimal
    timing_tolerance_days: int


@dataclass(frozen=True)
class MatchCandidateLine:
    snapshot_line_id: UUID
    entity_id: UUID
    account_code: str
    local_amount: Decimal
    expected_rate: Decimal
    parent_amount: Decimal
    ic_reference: str | None
    ic_counterparty_entity: UUID | None
    transaction_date: date | None
    ic_account_class: str | None


@dataclass(frozen=True)
class IntercompanyMatchDecision:
    match_key_hash: str
    entity_from: UUID
    entity_to: UUID
    account_code: str
    ic_reference: str | None
    amount_local_from: Decimal
    amount_local_to: Decimal
    amount_parent_from: Decimal
    amount_parent_to: Decimal
    expected_difference: Decimal
    actual_difference: Decimal
    fx_explained: Decimal
    unexplained_difference: Decimal
    classification: str
    transaction_date_from: date | None
    transaction_date_to: date | None


def _ordered_pair(entity_a: UUID, entity_b: UUID) -> tuple[UUID, UUID]:
    return (entity_a, entity_b) if str(entity_a) <= str(entity_b) else (entity_b, entity_a)


def _classify_pair(
    *,
    expected_difference: Decimal,
    actual_difference: Decimal,
    tolerance: IntercompanyToleranceConfig,
    transaction_date_from: date | None,
    transaction_date_to: date | None,
) -> tuple[str, Decimal, Decimal]:
    abs_actual = abs(actual_difference)
    if abs_actual <= tolerance.amount_tolerance_parent:
        return "matched", Decimal("0"), Decimal("0")

    variance = compute_fx_variance(
        expected_difference=expected_difference,
        actual_difference=actual_difference,
    ).fx_variance
    abs_variance = abs(variance)
    if abs_variance <= tolerance.fx_explained_tolerance_parent:
        return "fx_explained", quantize_persisted_amount(variance), Decimal("0")

    if transaction_date_from is not None and transaction_date_to is not None:
        if abs((transaction_date_from - transaction_date_to).days) <= tolerance.timing_tolerance_days:
            return "timing_difference", Decimal("0"), quantize_persisted_amount(actual_difference)

    return "unexplained", Decimal("0"), quantize_persisted_amount(actual_difference)


def _build_decision(
    *,
    key_seed: str,
    line_from: MatchCandidateLine,
    line_to: MatchCandidateLine,
    tolerance: IntercompanyToleranceConfig,
) -> IntercompanyMatchDecision:
    expected_difference = quantize_persisted_amount(
        (line_from.local_amount * line_from.expected_rate)
        + (line_to.local_amount * line_to.expected_rate)
    )
    actual_difference = quantize_persisted_amount(
        line_from.parent_amount + line_to.parent_amount
    )
    classification, fx_explained, unexplained_difference = _classify_pair(
        expected_difference=expected_difference,
        actual_difference=actual_difference,
        tolerance=tolerance,
        transaction_date_from=line_from.transaction_date,
        transaction_date_to=line_to.transaction_date,
    )
    payload = "|".join(
        [
            key_seed,
            str(line_from.snapshot_line_id),
            str(line_to.snapshot_line_id),
            classification,
        ]
    )
    pair_a, pair_b = _ordered_pair(line_from.entity_id, line_to.entity_id)
    return IntercompanyMatchDecision(
        match_key_hash=sha256_hex_text(payload),
        entity_from=pair_a,
        entity_to=pair_b,
        account_code=line_from.account_code,
        ic_reference=line_from.ic_reference or line_to.ic_reference,
        amount_local_from=quantize_persisted_amount(line_from.local_amount),
        amount_local_to=quantize_persisted_amount(line_to.local_amount),
        amount_parent_from=quantize_persisted_amount(line_from.parent_amount),
        amount_parent_to=quantize_persisted_amount(line_to.parent_amount),
        expected_difference=expected_difference,
        actual_difference=actual_difference,
        fx_explained=fx_explained,
        unexplained_difference=unexplained_difference,
        classification=classification,
        transaction_date_from=line_from.transaction_date,
        transaction_date_to=line_to.transaction_date,
    )


def match_intercompany_lines(
    *,
    lines: list[MatchCandidateLine],
    tolerance: IntercompanyToleranceConfig,
) -> list[IntercompanyMatchDecision]:
    ordered_lines = sorted(
        lines,
        key=lambda row: (
            str(row.entity_id),
            row.account_code,
            str(row.snapshot_line_id),
        ),
    )
    matched_ids: set[UUID] = set()
    decisions: list[IntercompanyMatchDecision] = []

    # Tier 1: ic_reference + ordered entity pair + account_code.
    tier1_groups: dict[tuple[str, UUID, UUID, str], list[MatchCandidateLine]] = {}
    for line in ordered_lines:
        if not line.ic_reference or line.ic_counterparty_entity is None:
            continue
        entity_a, entity_b = _ordered_pair(line.entity_id, line.ic_counterparty_entity)
        tier1_key = (line.ic_reference, entity_a, entity_b, line.account_code)
        tier1_groups.setdefault(tier1_key, []).append(line)

    for (ic_reference, entity_a, entity_b, account_code), group in sorted(
        tier1_groups.items(),
        key=lambda item: (item[0][0], str(item[0][1]), str(item[0][2]), item[0][3]),
    ):
        from_candidates = [row for row in group if row.entity_id == entity_a and row.snapshot_line_id not in matched_ids]
        to_candidates = [row for row in group if row.entity_id == entity_b and row.snapshot_line_id not in matched_ids]
        if not from_candidates or not to_candidates:
            continue
        line_from = sorted(from_candidates, key=lambda row: str(row.snapshot_line_id))[0]
        line_to = sorted(to_candidates, key=lambda row: str(row.snapshot_line_id))[0]
        decisions.append(
            _build_decision(
                key_seed=f"tier1|{ic_reference}|{entity_a}|{entity_b}|{account_code}",
                line_from=line_from,
                line_to=line_to,
                tolerance=tolerance,
            )
        )
        matched_ids.add(line_from.snapshot_line_id)
        matched_ids.add(line_to.snapshot_line_id)

    # Tier 2: counterparty_entity + ordered entity pair + mirrored ic_account_class.
    unmatched = [row for row in ordered_lines if row.snapshot_line_id not in matched_ids]
    for line in unmatched:
        if line.snapshot_line_id in matched_ids:
            continue
        if line.ic_counterparty_entity is None or not line.ic_account_class:
            continue
        mirrored = MIRRORED_IC_ACCOUNT_CLASS.get(line.ic_account_class)
        if mirrored is None:
            continue
        candidates = [
            row
            for row in unmatched
            if row.snapshot_line_id not in matched_ids
            and row.entity_id == line.ic_counterparty_entity
            and row.ic_counterparty_entity == line.entity_id
            and row.ic_account_class == mirrored
        ]
        if not candidates:
            continue
        candidate = sorted(candidates, key=lambda row: str(row.snapshot_line_id))[0]
        decisions.append(
            _build_decision(
                key_seed=(
                    f"tier2|{line.entity_id}|{candidate.entity_id}|"
                    f"{line.ic_account_class}|{mirrored}"
                ),
                line_from=line,
                line_to=candidate,
                tolerance=tolerance,
            )
        )
        matched_ids.add(line.snapshot_line_id)
        matched_ids.add(candidate.snapshot_line_id)

    # Unmatched IC lines are explicit unexplained records (not silently ignored).
    for line in ordered_lines:
        if line.snapshot_line_id in matched_ids:
            continue
        if not line.ic_reference and line.ic_counterparty_entity is None:
            continue
        synthetic = MatchCandidateLine(
            snapshot_line_id=line.snapshot_line_id,
            entity_id=line.ic_counterparty_entity or line.entity_id,
            account_code=line.account_code,
            local_amount=Decimal("0"),
            expected_rate=Decimal("1.000000"),
            parent_amount=Decimal("0"),
            ic_reference=line.ic_reference,
            ic_counterparty_entity=line.entity_id,
            transaction_date=None,
            ic_account_class=None,
        )
        decisions.append(
            _build_decision(
                key_seed=f"unmatched|{line.snapshot_line_id}",
                line_from=line,
                line_to=synthetic,
                tolerance=tolerance,
            )
        )

    decisions.sort(key=lambda row: row.match_key_hash)
    return decisions

