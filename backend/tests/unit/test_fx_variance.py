from __future__ import annotations

from decimal import Decimal

from financeops.services.fx.variance import compute_fx_variance


def test_compute_fx_variance_expected_vs_actual() -> None:
    result = compute_fx_variance(
        expected_difference=Decimal("1000.000000"),
        actual_difference=Decimal("1075.000000"),
    )
    assert result.expected_difference == Decimal("1000.000000")
    assert result.actual_difference == Decimal("1075.000000")
    assert result.fx_variance == Decimal("75.000000")
