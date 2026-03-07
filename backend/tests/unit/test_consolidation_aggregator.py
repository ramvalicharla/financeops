from __future__ import annotations

from decimal import Decimal

from financeops.services.consolidation.consolidation_aggregator import (
    AggregationEliminationInput,
    AggregationLineInput,
    aggregate_consolidation,
)


def test_aggregate_consolidation_applies_only_applied_eliminations() -> None:
    output = aggregate_consolidation(
        lines=[
            AggregationLineInput(
                account_code="4000",
                parent_amount=Decimal("100.000000"),
                fx_delta_component=Decimal("2.000000"),
            ),
            AggregationLineInput(
                account_code="4000",
                parent_amount=Decimal("50.000000"),
                fx_delta_component=Decimal("1.000000"),
            ),
            AggregationLineInput(
                account_code="5000",
                parent_amount=Decimal("-20.000000"),
                fx_delta_component=Decimal("0.500000"),
            ),
        ],
        eliminations=[
            AggregationEliminationInput(
                account_code="4000",
                elimination_status="applied",
                eliminated_amount_parent=Decimal("-10.000000"),
                fx_component_impact_parent=Decimal("0.200000"),
            ),
            AggregationEliminationInput(
                account_code="5000",
                elimination_status="blocked",
                eliminated_amount_parent=Decimal("-999.000000"),
                fx_component_impact_parent=Decimal("-999.000000"),
            ),
        ],
    )

    assert [row.consolidated_account_code for row in output.rows] == ["4000", "5000"]
    row_4000 = output.rows[0]
    row_5000 = output.rows[1]
    assert row_4000.consolidated_amount_parent == Decimal("140.000000")
    assert row_4000.fx_impact_total == Decimal("3.200000")
    assert row_5000.consolidated_amount_parent == Decimal("-20.000000")
    assert row_5000.fx_impact_total == Decimal("0.500000")
    assert output.total_consolidated_amount_parent == Decimal("120.000000")
    assert output.total_fx_impact_parent == Decimal("3.700000")
