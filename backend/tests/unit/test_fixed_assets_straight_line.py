from __future__ import annotations

from datetime import date
from decimal import Decimal

from financeops.services.fixed_assets.depreciation_methods.straight_line import (
    compute_straight_line_rows,
)


def test_straight_line_rows_use_actual_actual_partial_periods() -> None:
    rows = compute_straight_line_rows(
        opening_carrying_amount_reporting_currency=Decimal("1200.000000"),
        residual_value_reporting_currency=Decimal("0.000000"),
        useful_life_months=2,
        periods=[
            (1, date(2026, 1, 10), date(2026, 1, 31), date(2026, 1, 31)),
            (2, date(2026, 2, 1), date(2026, 2, 28), date(2026, 2, 28)),
        ],
    )
    assert len(rows) == 2
    assert rows[0].depreciation_amount_reporting_currency == Decimal("425.806452")
    assert rows[1].depreciation_amount_reporting_currency == Decimal("774.193548")


def test_straight_line_assigns_drift_to_final_row() -> None:
    rows = compute_straight_line_rows(
        opening_carrying_amount_reporting_currency=Decimal("100.000000"),
        residual_value_reporting_currency=Decimal("0.000000"),
        useful_life_months=3,
        periods=[
            (1, date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 31)),
            (2, date(2026, 2, 1), date(2026, 2, 28), date(2026, 2, 28)),
            (3, date(2026, 3, 1), date(2026, 3, 31), date(2026, 3, 31)),
        ],
    )
    amounts = [row.depreciation_amount_reporting_currency for row in rows]
    assert sum(amounts, start=Decimal("0.000000")) == Decimal("100.000000")
    assert amounts[0] == Decimal("33.333333")
    assert amounts[1] == Decimal("33.333333")
    assert amounts[2] == Decimal("33.333334")
