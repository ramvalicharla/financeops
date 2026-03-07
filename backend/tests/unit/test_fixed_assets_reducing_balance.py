from __future__ import annotations

from datetime import date
from decimal import Decimal

from financeops.services.fixed_assets.depreciation_methods.reducing_balance import (
    compute_reducing_balance_rows,
    reducing_balance_monthly_rate,
)


def test_reducing_balance_uses_locked_monthly_rate_formula() -> None:
    assert reducing_balance_monthly_rate(Decimal("0.120000")) == Decimal("0.010596")


def test_reducing_balance_respects_residual_floor() -> None:
    rows = compute_reducing_balance_rows(
        opening_carrying_amount_reporting_currency=Decimal("100.000000"),
        residual_value_reporting_currency=Decimal("95.000000"),
        annual_rate=Decimal("0.500000"),
        periods=[
            (1, date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 31)),
            (2, date(2026, 2, 1), date(2026, 2, 28), date(2026, 2, 28)),
        ],
    )
    assert rows
    total = sum((row.depreciation_amount_reporting_currency for row in rows), start=Decimal("0.000000"))
    assert total <= Decimal("5.000000")
