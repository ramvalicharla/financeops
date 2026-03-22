from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount
from financeops.services.consolidation.ic_matcher import IntercompanyMatchDecision


@dataclass(frozen=True)
class EliminationDecision:
    intercompany_pair_id: UUID
    entity_from: UUID
    entity_to: UUID
    account_code: str
    classification_at_time: str
    elimination_status: str
    eliminated_amount_parent: Decimal
    fx_component_impact_parent: Decimal
    residual_difference_parent: Decimal
    rule_code: str
    reason: str


def build_elimination_decisions(
    *,
    pair_ids: dict[str, UUID],
    pairs: list[IntercompanyMatchDecision],
) -> list[EliminationDecision]:
    decisions: list[EliminationDecision] = []
    for pair in pairs:
        pair_id = pair_ids[pair.match_key_hash]
        if pair.classification in {"matched", "fx_explained"}:
            decisions.append(
                EliminationDecision(
                    intercompany_pair_id=pair_id,
                    entity_from=pair.entity_from,
                    entity_to=pair.entity_to,
                    account_code=pair.account_code,
                    classification_at_time=pair.classification,
                    elimination_status="applied",
                    eliminated_amount_parent=quantize_persisted_amount(
                        Decimal("0") - (pair.amount_parent_from + pair.amount_parent_to)
                    ),
                    fx_component_impact_parent=(
                        quantize_persisted_amount(pair.fx_explained)
                        if pair.classification == "fx_explained"
                        else Decimal("0.000000")
                    ),
                    residual_difference_parent=Decimal("0.000000"),
                    rule_code=(
                        "ELIM.APPLY.MATCHED"
                        if pair.classification == "matched"
                        else "ELIM.APPLY.FX_EXPLAINED"
                    ),
                    reason="Applied elimination per deterministic IC classification",
                )
            )
            continue

        decisions.append(
            EliminationDecision(
                intercompany_pair_id=pair_id,
                entity_from=pair.entity_from,
                entity_to=pair.entity_to,
                account_code=pair.account_code,
                classification_at_time=pair.classification,
                elimination_status="blocked",
                eliminated_amount_parent=Decimal("0.000000"),
                fx_component_impact_parent=Decimal("0.000000"),
                residual_difference_parent=quantize_persisted_amount(pair.unexplained_difference),
                rule_code=(
                    "ELIM.BLOCK.TIMING"
                    if pair.classification == "timing_difference"
                    else "ELIM.BLOCK.UNEXPLAINED"
                ),
                reason=(
                    "Elimination blocked due to timing difference"
                    if pair.classification == "timing_difference"
                    else "Elimination blocked due to unexplained difference"
                ),
            )
        )
    decisions.sort(key=lambda row: str(row.intercompany_pair_id))
    return decisions

