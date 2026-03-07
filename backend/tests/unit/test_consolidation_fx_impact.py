from __future__ import annotations

from decimal import Decimal

from financeops.services.consolidation.fx_impact_calculator import (
    compute_fx_delta_component,
    quantize_output_amount,
    quantize_persisted_amount,
    quantize_rate,
)


def test_fx_delta_formula_and_quantization() -> None:
    parent_amount = Decimal("105.123456")
    local_amount = Decimal("100.000000")
    expected_rate = Decimal("1.000000")

    delta = compute_fx_delta_component(
        parent_amount=parent_amount,
        local_amount=local_amount,
        expected_rate=expected_rate,
    )

    assert delta == Decimal("5.123456")
    assert quantize_rate(Decimal("1.23456789")) == Decimal("1.234568")
    assert quantize_persisted_amount(Decimal("2.5555555")) == Decimal("2.555556")
    assert quantize_output_amount(Decimal("2.555")) == Decimal("2.56")
