from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.schemas.lease import LeaseRateMode
from financeops.services.lease.lease_registry import RegisteredLease
from financeops.services.lease.liability_schedule import (
    generate_liability_schedule_rows,
    resolve_lease_fx_rate,
)
from financeops.services.lease.payment_schedule import RegisteredLeasePayment


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_generate_liability_schedule_rows_deterministic(async_session: AsyncSession, test_tenant) -> None:
    lease = RegisteredLease(
        lease_id=_uuid("00000000-0000-0000-0000-000000001101"),
        lease_number="LEASE-LIA-1",
        lease_currency="USD",
        commencement_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
        payment_frequency="monthly",
        initial_discount_rate=Decimal("0.120000"),
        source_lease_reference="SRC-LIA-1",
    )
    payments = [
        RegisteredLeasePayment(
            payment_id=_uuid("00000000-0000-0000-0000-000000001102"),
            lease_id=lease.lease_id,
            lease_number=lease.lease_number,
            payment_date=date(2026, 1, 31),
            payment_amount_lease_currency=Decimal("100.000000"),
            payment_type="fixed",
            payment_sequence=1,
            source_lease_reference=lease.source_lease_reference,
        )
    ]

    with patch(
        "financeops.services.lease.liability_schedule.resolve_lease_fx_rate",
        new=AsyncMock(return_value=Decimal("1.000000")),
    ):
        output = await generate_liability_schedule_rows(
            async_session,
            tenant_id=test_tenant.id,
            leases=[lease],
            payments=payments,
            reporting_currency="USD",
            rate_mode=LeaseRateMode.daily,
        )

    assert len(output.rows) == 1
    row = output.rows[0]
    assert row.opening_liability_reporting_currency > Decimal("0")
    assert row.interest_expense_reporting_currency > Decimal("0")
    assert row.payment_amount_reporting_currency == Decimal("100.000000")


@pytest.mark.asyncio
async def test_month_end_locked_rate_missing_raises(async_session: AsyncSession, test_tenant) -> None:
    with patch(
        "financeops.services.lease.liability_schedule.list_manual_monthly_rates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(ValidationError):
            await resolve_lease_fx_rate(
                async_session,
                tenant_id=test_tenant.id,
                lease_currency="EUR",
                reporting_currency="USD",
                schedule_date=date(2026, 3, 10),
                rate_mode=LeaseRateMode.month_end_locked,
            )


@pytest.mark.asyncio
async def test_daily_rate_resolution_uses_selected_rate_service(async_session: AsyncSession, test_tenant) -> None:
    decision = type("Decision", (), {"selected_rate": Decimal("1.250000")})
    with patch(
        "financeops.services.lease.liability_schedule.resolve_selected_rate",
        new=AsyncMock(return_value=decision),
    ) as resolve_spy:
        rate = await resolve_lease_fx_rate(
            async_session,
            tenant_id=test_tenant.id,
            lease_currency="EUR",
            reporting_currency="USD",
            schedule_date=date(2026, 3, 10),
            rate_mode=LeaseRateMode.daily,
        )
    assert rate == Decimal("1.250000")
    assert resolve_spy.await_count == 1
