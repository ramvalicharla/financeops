from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.schemas.lease import LeaseInput
from financeops.services.lease.lease_registry import register_leases
from financeops.services.lease.payment_schedule import build_payment_timeline, register_lease_payments


def _lease_payload() -> LeaseInput:
    return LeaseInput.model_validate(
        {
            "lease_number": "LEASE-PAY-001",
            "counterparty_id": "CP-1",
            "lease_currency": "USD",
            "commencement_date": "2026-01-01",
            "end_date": "2026-03-31",
            "payment_frequency": "monthly",
            "initial_discount_rate": "0.120000",
            "discount_rate_source": "policy",
            "discount_rate_reference_date": "2026-01-01",
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": "SRC-LEASE-PAY-001",
            "policy_code": "ASC842",
            "policy_version": "v1",
            "payments": [
                {
                    "payment_date": "2026-03-31",
                    "payment_amount_lease_currency": "120.000000",
                    "payment_type": "fixed",
                    "payment_sequence": 3,
                },
                {
                    "payment_date": "2026-01-31",
                    "payment_amount_lease_currency": "100.000000",
                    "payment_type": "fixed",
                    "payment_sequence": 1,
                },
                {
                    "payment_date": "2026-02-28",
                    "payment_amount_lease_currency": "110.000000",
                    "payment_type": "fixed",
                    "payment_sequence": 2,
                },
            ],
            "modifications": [],
            "impairments": [],
        }
    )


@pytest.mark.asyncio
async def test_register_lease_payments_and_timeline_ordering(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    lease_input = _lease_payload()
    leases = await register_leases(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-lease-pay",
        leases=[lease_input],
    )
    payments = await register_lease_payments(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-lease-pay",
        leases=[lease_input],
        registered_leases=leases,
    )

    timeline = build_payment_timeline(lease_id=leases[0].lease_id, payments=payments)
    assert [item.payment_sequence for item in timeline] == [1, 2, 3]
    assert [item.payment_date for item in timeline] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
