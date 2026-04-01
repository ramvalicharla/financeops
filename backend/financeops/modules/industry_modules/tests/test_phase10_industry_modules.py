from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financeops.core.exceptions import ValidationError
from financeops.modules.industry_modules.application.service import (
    build_asset_projection,
    build_lease_projection,
    split_evenly,
    _months_between_inclusive,
)


class TestScheduleMath:
    def test_split_evenly_preserves_total(self) -> None:
        total = Decimal("1000.0000")
        rows = split_evenly(total, 3)
        assert len(rows) == 3
        assert sum(rows) == total

    def test_split_evenly_rejects_zero_parts(self) -> None:
        with pytest.raises(ValidationError):
            split_evenly(Decimal("100"), 0)

    def test_months_between_inclusive(self) -> None:
        rows = _months_between_inclusive(date(2026, 1, 15), date(2026, 4, 15))
        assert rows == [
            date(2026, 1, 15),
            date(2026, 2, 15),
            date(2026, 3, 15),
            date(2026, 4, 15),
        ]

    def test_lease_projection_zero_rate(self) -> None:
        pv, rows = build_lease_projection(
            lease_payment=Decimal("1000"),
            annual_discount_rate=Decimal("0"),
            period_count=12,
        )
        assert pv == Decimal("12000.0000")
        assert len(rows) == 12
        assert rows[-1].closing_liability == Decimal("0.0000")

    def test_lease_projection_balance_shape(self) -> None:
        pv, rows = build_lease_projection(
            lease_payment=Decimal("5000"),
            annual_discount_rate=Decimal("0.12"),
            period_count=24,
        )
        assert pv > Decimal("0")
        assert rows[0].opening_liability == pv
        assert rows[-1].closing_liability == Decimal("0.0000")
        assert all(row.depreciation >= Decimal("0") for row in rows)

    def test_asset_projection_slm_reaches_residual(self) -> None:
        rows = build_asset_projection(
            cost=Decimal("100000"),
            residual_value=Decimal("10000"),
            period_count=12,
            depreciation_method="SLM",
        )
        assert len(rows) == 12
        assert rows[-1].net_book_value == Decimal("10000.0000")

    def test_asset_projection_wdv_reaches_residual(self) -> None:
        rows = build_asset_projection(
            cost=Decimal("200000"),
            residual_value=Decimal("20000"),
            period_count=24,
            depreciation_method="WDV",
        )
        assert len(rows) == 24
        assert rows[-1].net_book_value == Decimal("20000.0000")

    def test_asset_projection_invalid_method(self) -> None:
        with pytest.raises(ValidationError):
            build_asset_projection(
                cost=Decimal("100"),
                residual_value=Decimal("0"),
                period_count=4,
                depreciation_method="XYZ",
            )

