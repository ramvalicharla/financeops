from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.services.lease.interest_engine import compute_period_interest


@pytest.mark.asyncio
async def test_interest_engine_is_deterministic() -> None:
    first = compute_period_interest(
        opening_liability_reporting_currency=Decimal("1200.000000"),
        annual_discount_rate=Decimal("0.120000"),
        payment_frequency="monthly",
    )
    second = compute_period_interest(
        opening_liability_reporting_currency=Decimal("1200.000000"),
        annual_discount_rate=Decimal("0.120000"),
        payment_frequency="monthly",
    )
    assert first == second
    assert first == Decimal("12.000000")
