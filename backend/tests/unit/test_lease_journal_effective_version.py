from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import (
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeaseModification,
    LeasePayment,
    LeaseRouSchedule,
    LeaseRun,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.lease.service_facade import build_journal_preview_for_run


@pytest.mark.asyncio
async def test_lease_journal_preview_filters_to_effective_schedule_version(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    correlation_id = "corr-lease-effective-journal"
    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "lease-effective-journal", "workflow_id": "wf-lease-effective"},
        values={
            "request_signature": "lease-effective-journal",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "leases": []},
            "workflow_id": "wf-lease-effective",
            "correlation_id": correlation_id,
        },
    )
    lease = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Lease,
        tenant_id=test_tenant.id,
        record_data={"lease_number": "LEASE-EFFECTIVE"},
        values={
            "lease_number": "LEASE-EFFECTIVE",
            "counterparty_id": "CP-EFFECTIVE",
            "lease_currency": "USD",
            "commencement_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "payment_frequency": "monthly",
            "initial_discount_rate": Decimal("0.100000"),
            "discount_rate_source": "policy",
            "discount_rate_reference_date": date(2026, 1, 1),
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": "SRC-LEASE-EFFECTIVE",
            "policy_code": "ASC842",
            "policy_version": "v1",
            "parent_reference_id": None,
            "source_reference_id": None,
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )
    payment = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeasePayment,
        tenant_id=test_tenant.id,
        record_data={"lease_id": str(lease.id), "payment_sequence": 1},
        values={
            "lease_id": lease.id,
            "payment_date": date(2026, 1, 31),
            "payment_amount_lease_currency": Decimal("100.000000"),
            "payment_type": "fixed",
            "payment_sequence": 1,
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": lease.id,
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    root_liability = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "lease_id": str(lease.id),
            "schedule_date": "2026-01-31",
            "schedule_version_token": "root",
            "period_seq": 1,
        },
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "payment_id": payment.id,
            "period_seq": 1,
            "schedule_date": date(2026, 1, 31),
            "period_year": 2026,
            "period_month": 1,
            "schedule_version_token": "root",
            "opening_liability_reporting_currency": Decimal("100.000000"),
            "interest_expense_reporting_currency": Decimal("1.000000"),
            "payment_amount_reporting_currency": Decimal("0.000000"),
            "closing_liability_reporting_currency": Decimal("101.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": payment.id,
            "correlation_id": correlation_id,
        },
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRouSchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "lease_id": str(lease.id),
            "schedule_date": "2026-01-31",
            "schedule_version_token": "root",
            "period_seq": 1,
        },
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "period_seq": 1,
            "schedule_date": date(2026, 1, 31),
            "period_year": 2026,
            "period_month": 1,
            "schedule_version_token": "root",
            "opening_rou_reporting_currency": Decimal("100.000000"),
            "amortization_expense_reporting_currency": Decimal("10.000000"),
            "impairment_amount_reporting_currency": Decimal("0.000000"),
            "closing_rou_reporting_currency": Decimal("90.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": lease.id,
            "correlation_id": correlation_id,
        },
    )

    effective_liability = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "lease_id": str(lease.id),
            "schedule_date": "2026-01-31",
            "schedule_version_token": "v2",
            "period_seq": 1,
        },
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "payment_id": payment.id,
            "period_seq": 1,
            "schedule_date": date(2026, 1, 31),
            "period_year": 2026,
            "period_month": 1,
            "schedule_version_token": "v2",
            "opening_liability_reporting_currency": Decimal("120.000000"),
            "interest_expense_reporting_currency": Decimal("2.000000"),
            "payment_amount_reporting_currency": Decimal("0.000000"),
            "closing_liability_reporting_currency": Decimal("122.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": payment.id,
            "correlation_id": correlation_id,
        },
    )
    effective_rou = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRouSchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "lease_id": str(lease.id),
            "schedule_date": "2026-01-31",
            "schedule_version_token": "v2",
            "period_seq": 1,
        },
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "period_seq": 1,
            "schedule_date": date(2026, 1, 31),
            "period_year": 2026,
            "period_month": 1,
            "schedule_version_token": "v2",
            "opening_rou_reporting_currency": Decimal("120.000000"),
            "amortization_expense_reporting_currency": Decimal("12.000000"),
            "impairment_amount_reporting_currency": Decimal("0.000000"),
            "closing_rou_reporting_currency": Decimal("108.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": lease.id,
            "correlation_id": correlation_id,
        },
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseModification,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "lease_id": str(lease.id),
            "effective_date": "2026-02-01",
            "idempotency_key": "idem-lease-effective",
        },
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "effective_date": date(2026, 2, 1),
            "modification_type": "term_change",
            "modification_reason": "effective token swap",
            "idempotency_key": "idem-lease-effective",
            "prior_schedule_version_token": "root",
            "new_schedule_version_token": "v2",
            "prior_schedule_reference": str(root_liability.id),
            "new_schedule_reference": str(effective_liability.id),
            "remeasurement_delta_reporting_currency": Decimal("0.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": root_liability.id,
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    result = await build_journal_preview_for_run(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        user_id=test_tenant.id,
        correlation_id=correlation_id,
    )
    assert result["journal_count"] == 2

    journal_rows = (
        await async_session.execute(
            select(LeaseJournalEntry).where(
                LeaseJournalEntry.tenant_id == test_tenant.id,
                LeaseJournalEntry.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(journal_rows) == 2

    assert {row.liability_schedule_id for row in journal_rows if row.liability_schedule_id is not None} == {
        effective_liability.id
    }
    assert {row.rou_schedule_id for row in journal_rows if row.rou_schedule_id is not None} == {
        effective_rou.id
    }
