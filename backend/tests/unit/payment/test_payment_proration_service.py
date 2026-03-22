from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.payment.application.proration_service import ProrationService


def test_proration_calculation_returns_expected_values() -> None:
    result = ProrationService.calculate(
        from_plan_price=Decimal("100.00"),
        to_plan_price=Decimal("200.00"),
        days_remaining=15,
        total_days=30,
        currency="usd",
    )
    assert result.credit_amount == Decimal("50.00")
    assert result.debit_amount == Decimal("100.00")
    assert result.net_adjustment == Decimal("50.00")
    assert result.currency == "USD"


def test_proration_rejects_invalid_total_days() -> None:
    with pytest.raises(ValueError):
        ProrationService.calculate(
            from_plan_price=Decimal("100.00"),
            to_plan_price=Decimal("200.00"),
            days_remaining=10,
            total_days=0,
            currency="INR",
        )

