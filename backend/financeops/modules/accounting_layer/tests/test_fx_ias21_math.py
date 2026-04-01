from __future__ import annotations

from decimal import Decimal

from financeops.services.fx.ias21_math import (
    compute_revaluation_delta,
    compute_translated_equity_and_cta,
)


def test_compute_revaluation_delta_gain() -> None:
    revalued_base, fx_difference = compute_revaluation_delta(
        foreign_balance=Decimal("100"),
        closing_rate=Decimal("83.4567"),
        historical_base_balance=Decimal("8200"),
    )
    assert revalued_base == Decimal("8345.6700")
    assert fx_difference == Decimal("145.6700")


def test_compute_revaluation_delta_loss() -> None:
    revalued_base, fx_difference = compute_revaluation_delta(
        foreign_balance=Decimal("50"),
        closing_rate=Decimal("79.1000"),
        historical_base_balance=Decimal("4000"),
    )
    assert revalued_base == Decimal("3955.0000")
    assert fx_difference == Decimal("-45.0000")


def test_compute_translated_equity_and_cta() -> None:
    translated_equity, cta_amount = compute_translated_equity_and_cta(
        assets=Decimal("1000"),
        liabilities=Decimal("600"),
        equity_total=Decimal("400"),
        retained_earnings=Decimal("100"),
        closing_rate=Decimal("80"),
        average_rate=Decimal("75"),
    )
    assert translated_equity == Decimal("31500.0000")
    assert cta_amount == Decimal("500.0000")


def test_compute_translated_equity_and_cta_zero_when_rates_equal() -> None:
    translated_equity, cta_amount = compute_translated_equity_and_cta(
        assets=Decimal("100"),
        liabilities=Decimal("60"),
        equity_total=Decimal("40"),
        retained_earnings=Decimal("10"),
        closing_rate=Decimal("1"),
        average_rate=Decimal("1"),
    )
    assert translated_equity == Decimal("40.0000")
    assert cta_amount == Decimal("0.0000")
