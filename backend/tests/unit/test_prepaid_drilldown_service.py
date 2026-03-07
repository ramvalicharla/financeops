from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prepaid import (
    Prepaid,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
    PrepaidRun,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.prepaid.drilldown_service import (
    get_journal_drill,
    get_prepaid_drill,
    get_schedule_drill,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_prepaid_drilldown_service_returns_lineage_navigation(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    correlation_id = "00000000-0000-0000-0000-000000011111"

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=PrepaidRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "ppd-drill", "workflow_id": "wf-ppd-drill"},
        values={
            "request_signature": "ppd-drill",
            "initiated_by": test_tenant.id,
            "configuration_json": {"prepaids": []},
            "workflow_id": "wf-ppd-drill",
            "correlation_id": correlation_id,
        },
    )

    prepaid = await AuditWriter.insert_financial_record(
        async_session,
        model_class=Prepaid,
        tenant_id=test_tenant.id,
        record_data={"prepaid_code": "PPD-DRILL-1", "source_expense_reference": "SRC-DRILL-1"},
        values={
            "prepaid_code": "PPD-DRILL-1",
            "description": "drill",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": date(2026, 1, 1),
            "term_end_date": date(2026, 3, 31),
            "base_amount_contract_currency": Decimal("300.000000"),
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "pattern_json_normalized": {"pattern_type": "straight_line", "periods": []},
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-DRILL-1",
            "parent_reference_id": None,
            "source_reference_id": _uuid("00000000-0000-0000-0000-000000011901"),
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    schedule = await AuditWriter.insert_financial_record(
        async_session,
        model_class=PrepaidAmortizationSchedule,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "period_seq": 1,
            "amortization_date": "2026-01-31",
            "schedule_version_token": "tok-drill",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "period_seq": 1,
            "amortization_date": date(2026, 1, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 1,
            "schedule_version_token": "tok-drill",
            "base_amount_contract_currency": Decimal("100.000000"),
            "amortized_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_amortized_reporting_currency": Decimal("100.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 1, 31),
            "fx_rate_source": "same_currency_1_0",
            "schedule_status": "scheduled",
            "source_expense_reference": prepaid.source_expense_reference,
            "parent_reference_id": prepaid.id,
            "source_reference_id": prepaid.source_reference_id,
            "correlation_id": correlation_id,
        },
    )

    journal = await AuditWriter.insert_financial_record(
        async_session,
        model_class=PrepaidJournalEntry,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "schedule_id": str(schedule.id),
            "journal_reference": "PPD-DRILL-1",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "schedule_id": schedule.id,
            "journal_reference": "PPD-DRILL-1",
            "entry_date": date(2026, 1, 31),
            "debit_account": "Prepaid Expense",
            "credit_account": "Prepaid Asset",
            "amount_reporting_currency": Decimal("100.000000"),
            "source_expense_reference": prepaid.source_expense_reference,
            "parent_reference_id": schedule.id,
            "source_reference_id": prepaid.source_reference_id,
            "correlation_id": correlation_id,
        },
    )

    prepaid_drill = await get_prepaid_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        prepaid_id=prepaid.id,
    )
    schedule_drill = await get_schedule_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        schedule_id=schedule.id,
    )
    journal_drill = await get_journal_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        journal_id=journal.id,
    )

    assert prepaid_drill["child_ids"] == [schedule.id]
    assert schedule_drill["child_ids"] == [prepaid.source_reference_id]
    assert journal_drill["child_ids"] == [schedule.id]
    assert str(prepaid_drill["correlation_id"]) == correlation_id
