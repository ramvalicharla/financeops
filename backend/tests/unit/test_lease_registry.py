from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.schemas.lease import LeaseInput
from financeops.services.audit_writer import AuditWriter
from financeops.services.lease.lease_registry import register_leases


def _lease_payload(lease_number: str) -> LeaseInput:
    return LeaseInput.model_validate(
        {
            "lease_number": lease_number,
            "counterparty_id": "CP-1",
            "lease_currency": "USD",
            "commencement_date": "2026-01-01",
            "end_date": "2026-12-31",
            "payment_frequency": "monthly",
            "initial_discount_rate": "0.120000",
            "discount_rate_source": "policy",
            "discount_rate_reference_date": "2026-01-01",
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": f"SRC-{lease_number}",
            "policy_code": "ASC842",
            "policy_version": "v1",
            "payments": [
                {
                    "payment_date": "2026-01-31",
                    "payment_amount_lease_currency": "100.000000",
                    "payment_type": "fixed",
                    "payment_sequence": 1,
                }
            ],
            "modifications": [],
            "impairments": [],
        }
    )


@pytest.mark.asyncio
async def test_register_leases_uses_audit_writer(async_session: AsyncSession, test_tenant) -> None:
    lease = _lease_payload("LEASE-100")
    with patch(
        "financeops.services.lease.lease_registry.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        rows = await register_leases(
            async_session,
            tenant_id=test_tenant.id,
            user_id=test_tenant.id,
            correlation_id="corr-lease-registry",
            leases=[lease],
        )
    assert len(rows) == 1
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_register_leases_is_idempotent_for_same_correlation(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    lease = _lease_payload("LEASE-200")
    first = await register_leases(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-lease-idempotent",
        leases=[lease],
    )
    second = await register_leases(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-lease-idempotent",
        leases=[lease],
    )
    assert first[0].lease_id == second[0].lease_id
