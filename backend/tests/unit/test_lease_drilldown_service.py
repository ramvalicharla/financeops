from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import (
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeasePayment,
    LeaseRouSchedule,
    LeaseRun,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.lease.drilldown_service import (
    get_journal_drill,
    get_lease_drill,
    get_liability_drill,
    get_payment_drill,
    get_rou_drill,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_lease_drilldown_service_returns_lineage_navigation(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    correlation_id = "00000000-0000-0000-0000-000000001355"

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "lease-drill", "workflow_id": "wf-lease-drill"},
        values={
            "request_signature": "lease-drill",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "leases": []},
            "workflow_id": "wf-lease-drill",
            "correlation_id": correlation_id,
        },
    )

    lease = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Lease,
        tenant_id=test_tenant.id,
        record_data={"lease_number": "LEASE-DRILL-1"},
        values={
            "lease_number": "LEASE-DRILL-1",
            "counterparty_id": "CP-DRILL",
            "lease_currency": "USD",
            "commencement_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "payment_frequency": "monthly",
            "initial_discount_rate": Decimal("0.120000"),
            "discount_rate_source": "policy",
            "discount_rate_reference_date": date(2026, 1, 1),
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": "SRC-LEASE-DRILL-1",
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

    liability = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "schedule_date": "2026-01-31"},
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
            "payment_amount_reporting_currency": Decimal("100.000000"),
            "closing_liability_reporting_currency": Decimal("1.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": payment.id,
            "correlation_id": correlation_id,
        },
    )

    rou = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseRouSchedule,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "schedule_date": "2026-01-31"},
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
            "source_reference_id": payment.id,
            "correlation_id": correlation_id,
        },
    )

    journal = await AuditWriter.insert_financial_record(
        async_session,
        model_class=LeaseJournalEntry,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "journal_reference": "LSE-DRILL-1"},
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "liability_schedule_id": liability.id,
            "rou_schedule_id": None,
            "journal_reference": "LSE-DRILL-1",
            "entry_date": date(2026, 1, 31),
            "debit_account": "Lease Expense",
            "credit_account": "Lease Liability",
            "amount_reporting_currency": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": liability.id,
            "source_reference_id": payment.id,
            "correlation_id": correlation_id,
        },
    )

    lease_drill = await get_lease_drill(async_session, tenant_id=test_tenant.id, run_id=run.id, lease_id=lease.id)
    payment_drill = await get_payment_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        payment_id=payment.id,
    )
    liability_drill = await get_liability_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        line_id=liability.id,
    )
    rou_drill = await get_rou_drill(async_session, tenant_id=test_tenant.id, run_id=run.id, line_id=rou.id)
    journal_drill = await get_journal_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        journal_id=journal.id,
    )

    assert lease_drill["child_ids"] == [payment.id]
    assert payment_drill["child_ids"] == [liability.id]
    assert liability_drill["child_ids"] == [payment.id]
    assert rou_drill["child_ids"] == [lease.id]
    assert journal_drill["child_ids"] == [liability.id]
