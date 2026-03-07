from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from financeops.services.lease.payment_schedule import RegisteredLeasePayment
from financeops.services.lease.pv_calculator import calculate_present_value


def _uuid(value: str) -> UUID:
    return UUID(value)


def _payments() -> list[RegisteredLeasePayment]:
    return [
        RegisteredLeasePayment(
            payment_id=_uuid("00000000-0000-0000-0000-000000001001"),
            lease_id=_uuid("00000000-0000-0000-0000-000000001099"),
            lease_number="LEASE-PV",
            payment_date=date(2026, 1, 31),
            payment_amount_lease_currency=Decimal("100.000000"),
            payment_type="fixed",
            payment_sequence=1,
            source_lease_reference="SRC-LEASE-PV",
        ),
        RegisteredLeasePayment(
            payment_id=_uuid("00000000-0000-0000-0000-000000001002"),
            lease_id=_uuid("00000000-0000-0000-0000-000000001099"),
            lease_number="LEASE-PV",
            payment_date=date(2026, 2, 28),
            payment_amount_lease_currency=Decimal("100.000000"),
            payment_type="fixed",
            payment_sequence=2,
            source_lease_reference="SRC-LEASE-PV",
        ),
    ]


@pytest.mark.asyncio
async def test_present_value_calculation_is_reproducible() -> None:
    first = calculate_present_value(
        lease_id=_uuid("00000000-0000-0000-0000-000000001099"),
        payments=_payments(),
        annual_discount_rate=Decimal("0.120000"),
        payment_frequency="monthly",
        conversion_rate=Decimal("1.000000"),
    )
    second = calculate_present_value(
        lease_id=_uuid("00000000-0000-0000-0000-000000001099"),
        payments=_payments(),
        annual_discount_rate=Decimal("0.120000"),
        payment_frequency="monthly",
        conversion_rate=Decimal("1.000000"),
    )

    assert first.present_value_reporting_currency == second.present_value_reporting_currency
    assert first.discount_rate_per_period == second.discount_rate_per_period
    assert first.present_value_reporting_currency > Decimal("0")
