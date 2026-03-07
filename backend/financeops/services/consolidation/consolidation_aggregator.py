from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount


@dataclass(frozen=True)
class AggregationLineInput:
    account_code: str
    parent_amount: Decimal
    fx_delta_component: Decimal


@dataclass(frozen=True)
class AggregationEliminationInput:
    account_code: str
    elimination_status: str
    eliminated_amount_parent: Decimal
    fx_component_impact_parent: Decimal


@dataclass(frozen=True)
class AggregatedAccountTotal:
    consolidated_account_code: str
    consolidated_amount_parent: Decimal
    fx_impact_total: Decimal


@dataclass(frozen=True)
class AggregationOutput:
    rows: list[AggregatedAccountTotal]
    total_consolidated_amount_parent: Decimal
    total_fx_impact_parent: Decimal


def aggregate_consolidation(
    *,
    lines: list[AggregationLineInput],
    eliminations: list[AggregationEliminationInput],
) -> AggregationOutput:
    bucket: dict[str, tuple[Decimal, Decimal]] = {}
    for line in lines:
        current_amount, current_fx = bucket.get(
            line.account_code,
            (Decimal("0.000000"), Decimal("0.000000")),
        )
        bucket[line.account_code] = (
            quantize_persisted_amount(current_amount + line.parent_amount),
            quantize_persisted_amount(current_fx + line.fx_delta_component),
        )

    for elimination in eliminations:
        if elimination.elimination_status != "applied":
            continue
        current_amount, current_fx = bucket.get(
            elimination.account_code,
            (Decimal("0.000000"), Decimal("0.000000")),
        )
        bucket[elimination.account_code] = (
            quantize_persisted_amount(current_amount + elimination.eliminated_amount_parent),
            quantize_persisted_amount(current_fx + elimination.fx_component_impact_parent),
        )

    rows = [
        AggregatedAccountTotal(
            consolidated_account_code=account_code,
            consolidated_amount_parent=quantize_persisted_amount(values[0]),
            fx_impact_total=quantize_persisted_amount(values[1]),
        )
        for account_code, values in sorted(bucket.items(), key=lambda item: item[0])
    ]
    total_amount = quantize_persisted_amount(
        sum((row.consolidated_amount_parent for row in rows), start=Decimal("0.000000"))
    )
    total_fx = quantize_persisted_amount(
        sum((row.fx_impact_total for row in rows), start=Decimal("0.000000"))
    )
    return AggregationOutput(
        rows=rows,
        total_consolidated_amount_parent=total_amount,
        total_fx_impact_parent=total_fx,
    )
