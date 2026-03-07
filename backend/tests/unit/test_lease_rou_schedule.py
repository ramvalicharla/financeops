from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from financeops.services.lease.lease_registry import RegisteredLease
from financeops.services.lease.liability_schedule import LeaseLiabilityScheduleRow
from financeops.services.lease.rou_schedule import generate_rou_schedule_rows


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_generate_rou_schedule_rows_with_impairment() -> None:
    lease = RegisteredLease(
        lease_id=_uuid("00000000-0000-0000-0000-000000001201"),
        lease_number="LEASE-ROU-1",
        lease_currency="USD",
        commencement_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
        payment_frequency="monthly",
        initial_discount_rate=Decimal("0.120000"),
        source_lease_reference="SRC-ROU-1",
    )
    liability_rows = [
        LeaseLiabilityScheduleRow(
            lease_id=lease.lease_id,
            payment_id=_uuid("00000000-0000-0000-0000-000000001202"),
            period_seq=1,
            schedule_date=date(2026, 1, 31),
            period_year=2026,
            period_month=1,
            schedule_version_token="root",
            opening_liability_reporting_currency=Decimal("200.000000"),
            interest_expense_reporting_currency=Decimal("2.000000"),
            payment_amount_reporting_currency=Decimal("100.000000"),
            closing_liability_reporting_currency=Decimal("102.000000"),
            fx_rate_used=Decimal("1.000000"),
            source_lease_reference=lease.source_lease_reference,
            parent_reference_id=lease.lease_id,
            source_reference_id=_uuid("00000000-0000-0000-0000-000000001202"),
        ),
        LeaseLiabilityScheduleRow(
            lease_id=lease.lease_id,
            payment_id=_uuid("00000000-0000-0000-0000-000000001203"),
            period_seq=2,
            schedule_date=date(2026, 2, 28),
            period_year=2026,
            period_month=2,
            schedule_version_token="root",
            opening_liability_reporting_currency=Decimal("102.000000"),
            interest_expense_reporting_currency=Decimal("1.020000"),
            payment_amount_reporting_currency=Decimal("100.000000"),
            closing_liability_reporting_currency=Decimal("3.020000"),
            fx_rate_used=Decimal("1.000000"),
            source_lease_reference=lease.source_lease_reference,
            parent_reference_id=lease.lease_id,
            source_reference_id=_uuid("00000000-0000-0000-0000-000000001203"),
        ),
    ]

    rows = generate_rou_schedule_rows(
        leases=[lease],
        liability_rows=liability_rows,
        impairments_by_lease={
            lease.lease_id: {
                date(2026, 2, 28): Decimal("5.000000"),
            }
        },
    )
    assert len(rows) == 2
    assert rows[0].opening_rou_reporting_currency == Decimal("200.000000")
    assert rows[1].impairment_amount_reporting_currency == Decimal("5.000000")
    assert rows[1].closing_rou_reporting_currency < rows[1].opening_rou_reporting_currency
