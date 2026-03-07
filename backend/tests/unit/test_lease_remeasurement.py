from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import Lease, LeaseLiabilitySchedule, LeaseModification, LeaseRun
from financeops.schemas.lease import LeaseInput
from financeops.services.audit_writer import AuditWriter
from financeops.services.lease.lease_registry import register_leases
from financeops.services.lease.remeasurement import apply_lease_modifications


def _lease_payload_with_modification() -> LeaseInput:
    return LeaseInput.model_validate(
        {
            "lease_number": "LEASE-REM-001",
            "counterparty_id": "CP-REM",
            "lease_currency": "USD",
            "commencement_date": "2026-01-01",
            "end_date": "2026-12-31",
            "payment_frequency": "monthly",
            "initial_discount_rate": "0.120000",
            "discount_rate_source": "policy",
            "discount_rate_reference_date": "2026-01-01",
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": "SRC-LEASE-REM-001",
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
            "modifications": [
                {
                    "effective_date": "2026-06-30",
                    "modification_type": "term_change",
                    "modification_reason": "Lease extended",
                    "new_discount_rate": "0.150000",
                    "new_end_date": "2027-03-31",
                    "remeasurement_delta_reporting_currency": "5.000000",
                }
            ],
            "impairments": [],
        }
    )


@pytest.mark.asyncio
async def test_apply_lease_modifications_creates_superseding_lease_and_modification(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    lease_input = _lease_payload_with_modification()
    registered_leases = await register_leases(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        correlation_id="corr-lease-rem-1",
        leases=[lease_input],
    )

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "lease-rem-signature", "workflow_id": "lease-rem-workflow"},
        values={
            "request_signature": "lease-rem-signature",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "leases": []},
            "workflow_id": "lease-rem-workflow",
            "correlation_id": "corr-lease-rem-1",
        },
    )

    current_lease = (
        await async_session.execute(select(Lease).where(Lease.id == registered_leases[0].lease_id))
    ).scalar_one()

    await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "lease_id": str(current_lease.id), "schedule_date": "2026-03-31"},
        values={
            "run_id": run.id,
            "lease_id": current_lease.id,
            "payment_id": None,
            "period_seq": 1,
            "schedule_date": date(2026, 3, 31),
            "period_year": 2026,
            "period_month": 3,
            "schedule_version_token": "root",
            "opening_liability_reporting_currency": Decimal("100.000000"),
            "interest_expense_reporting_currency": Decimal("1.000000"),
            "payment_amount_reporting_currency": Decimal("10.000000"),
            "closing_liability_reporting_currency": Decimal("91.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": current_lease.source_lease_reference,
            "parent_reference_id": current_lease.id,
            "source_reference_id": current_lease.id,
            "correlation_id": "corr-lease-rem-1",
        },
    )

    result = await apply_lease_modifications(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        run_id=run.id,
        correlation_id="corr-lease-rem-1",
        leases=[lease_input],
        registered_leases=registered_leases,
        root_schedule_version_tokens={current_lease.id: "root"},
        reporting_currency="USD",
        rate_mode="daily",
    )

    assert result.modification_count == 1

    modifications = (
        await async_session.execute(
            select(LeaseModification).where(
                LeaseModification.tenant_id == test_tenant.id,
                LeaseModification.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(modifications) == 1

    superseding = (
        await async_session.execute(
            select(Lease).where(
                Lease.tenant_id == test_tenant.id,
                Lease.supersedes_id == current_lease.id,
                Lease.initial_discount_rate == Decimal("0.150000"),
            )
        )
    ).scalars().all()
    assert len(superseding) == 1
    first_token = modifications[0].new_schedule_version_token

    replay = await apply_lease_modifications(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_tenant.id,
        run_id=run.id,
        correlation_id="corr-lease-rem-1",
        leases=[lease_input],
        registered_leases=registered_leases,
        root_schedule_version_tokens={current_lease.id: "root"},
        reporting_currency="USD",
        rate_mode="daily",
    )
    assert replay.modification_count == 0
    replay_mods = (
        await async_session.execute(
            select(LeaseModification).where(
                LeaseModification.tenant_id == test_tenant.id,
                LeaseModification.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(replay_mods) == 1
    assert replay_mods[0].new_schedule_version_token == first_token
