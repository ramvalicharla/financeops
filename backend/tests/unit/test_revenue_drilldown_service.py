from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.revenue import (
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueSchedule,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.revenue.drilldown_service import (
    get_contract_drill,
    get_journal_drill,
    get_obligation_drill,
    get_schedule_drill,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


@pytest.mark.asyncio
async def test_revenue_drilldown_service_returns_lineage_navigation(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    correlation_id = "00000000-0000-0000-0000-000000000955"

    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "rev-drill", "workflow_id": "wf-rev-drill"},
        values={
            "request_signature": "rev-drill",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "contracts": []},
            "workflow_id": "wf-rev-drill",
            "correlation_id": correlation_id,
        },
    )

    contract = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueContract,
        tenant_id=test_tenant.id,
        record_data={"contract_number": "REV-DRILL-1"},
        values={
            "contract_number": "REV-DRILL-1",
            "customer_id": "CUST-DRILL",
            "contract_currency": "USD",
            "contract_start_date": date(2026, 1, 1),
            "contract_end_date": date(2026, 3, 31),
            "total_contract_value": Decimal("300.000000"),
            "source_contract_reference": "SRC-DRILL-1",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    obligation = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenuePerformanceObligation,
        tenant_id=test_tenant.id,
        record_data={"obligation_code": "OBL-DRILL-1"},
        values={
            "contract_id": contract.id,
            "obligation_code": "OBL-DRILL-1",
            "description": "Drill obligation",
            "standalone_selling_price": Decimal("300.000000"),
            "allocation_basis": "ssp",
            "recognition_method": "straight_line",
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": contract.id,
            "source_reference_id": contract.id,
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    line_item = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueContractLineItem,
        tenant_id=test_tenant.id,
        record_data={"line_code": "LINE-DRILL-1"},
        values={
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "line_code": "LINE-DRILL-1",
            "line_amount": Decimal("300.000000"),
            "line_currency": "USD",
            "milestone_reference": None,
            "usage_reference": None,
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": obligation.id,
            "source_reference_id": contract.id,
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )

    schedule = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueSchedule,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "contract_line_item_id": str(line_item.id)},
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "contract_line_item_id": line_item.id,
            "period_seq": 1,
            "recognition_date": date(2026, 3, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 3,
            "schedule_version_token": "root",
            "recognition_method": "straight_line",
            "base_amount_contract_currency": Decimal("300.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "recognized_amount_reporting_currency": Decimal("300.000000"),
            "cumulative_recognized_reporting_currency": Decimal("300.000000"),
            "schedule_status": "recognized",
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": obligation.id,
            "source_reference_id": line_item.id,
            "correlation_id": correlation_id,
        },
    )

    journal = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueJournalEntry,
        tenant_id=test_tenant.id,
        record_data={"run_id": str(run.id), "schedule_id": str(schedule.id)},
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "schedule_id": schedule.id,
            "journal_reference": "REV-DRILL-000001",
            "entry_date": date(2026, 3, 31),
            "debit_account": "Accounts Receivable",
            "credit_account": "Revenue",
            "amount_reporting_currency": Decimal("300.000000"),
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": schedule.id,
            "source_reference_id": line_item.id,
            "correlation_id": correlation_id,
        },
    )

    contract_drill = await get_contract_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        contract_id=contract.id,
    )
    obligation_drill = await get_obligation_drill(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.id,
        obligation_id=obligation.id,
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

    assert contract_drill["child_ids"] == [obligation.id]
    assert obligation_drill["child_ids"] == [line_item.id]
    assert schedule_drill["child_ids"] == [line_item.id]
    assert journal_drill["child_ids"] == [schedule.id]
    assert str(contract_drill["correlation_id"]) == correlation_id
