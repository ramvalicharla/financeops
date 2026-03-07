from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.revenue import (
    RevenueAdjustment,
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueSchedule,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.revenue.service_facade import build_journal_preview_for_run


@pytest.mark.asyncio
async def test_revenue_journal_preview_filters_to_effective_schedule_version(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    correlation_id = "corr-rev-effective-journal"
    run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueRun,
        tenant_id=test_tenant.id,
        record_data={"request_signature": "rev-effective-journal", "workflow_id": "wf-rev-effective"},
        values={
            "request_signature": "rev-effective-journal",
            "initiated_by": test_tenant.id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "contracts": []},
            "workflow_id": "wf-rev-effective",
            "correlation_id": correlation_id,
        },
    )
    contract = await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueContract,
        tenant_id=test_tenant.id,
        record_data={"contract_number": "REV-EFFECTIVE"},
        values={
            "contract_number": "REV-EFFECTIVE",
            "customer_id": "CUST-EFFECTIVE",
            "contract_currency": "USD",
            "contract_start_date": date(2026, 1, 1),
            "contract_end_date": date(2026, 12, 31),
            "total_contract_value": Decimal("240.000000"),
            "source_contract_reference": "SRC-REV-EFFECTIVE",
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
        record_data={"obligation_code": "OBL-EFFECTIVE"},
        values={
            "contract_id": contract.id,
            "obligation_code": "OBL-EFFECTIVE",
            "description": "Effective version obligation",
            "standalone_selling_price": Decimal("240.000000"),
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
        record_data={"line_code": "LINE-EFFECTIVE"},
        values={
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "line_code": "LINE-EFFECTIVE",
            "line_amount": Decimal("240.000000"),
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

    root_rows: list[RevenueSchedule] = []
    effective_rows: list[RevenueSchedule] = []
    for period_seq, recognition_date in ((1, date(2026, 1, 31)), (2, date(2026, 2, 28))):
        root_rows.append(
            await AuditWriter.insert_financial_record(
                async_session,
                model_class=RevenueSchedule,
                tenant_id=test_tenant.id,
                record_data={
                    "run_id": str(run.id),
                    "contract_id": str(contract.id),
                    "recognition_date": recognition_date.isoformat(),
                    "schedule_version_token": "root",
                    "period_seq": period_seq,
                },
                values={
                    "run_id": run.id,
                    "contract_id": contract.id,
                    "obligation_id": obligation.id,
                    "contract_line_item_id": line_item.id,
                    "period_seq": period_seq,
                    "recognition_date": recognition_date,
                    "recognition_period_year": recognition_date.year,
                    "recognition_period_month": recognition_date.month,
                    "schedule_version_token": "root",
                    "recognition_method": "straight_line",
                    "base_amount_contract_currency": Decimal("120.000000"),
                    "fx_rate_used": Decimal("1.000000"),
                    "recognized_amount_reporting_currency": Decimal("120.000000"),
                    "cumulative_recognized_reporting_currency": Decimal(str(period_seq * 120)),
                    "schedule_status": "recognized",
                    "source_contract_reference": contract.source_contract_reference,
                    "parent_reference_id": contract.id,
                    "source_reference_id": line_item.id,
                    "correlation_id": correlation_id,
                },
            )
        )
        effective_rows.append(
            await AuditWriter.insert_financial_record(
                async_session,
                model_class=RevenueSchedule,
                tenant_id=test_tenant.id,
                record_data={
                    "run_id": str(run.id),
                    "contract_id": str(contract.id),
                    "recognition_date": recognition_date.isoformat(),
                    "schedule_version_token": "v2",
                    "period_seq": period_seq,
                },
                values={
                    "run_id": run.id,
                    "contract_id": contract.id,
                    "obligation_id": obligation.id,
                    "contract_line_item_id": line_item.id,
                    "period_seq": period_seq,
                    "recognition_date": recognition_date,
                    "recognition_period_year": recognition_date.year,
                    "recognition_period_month": recognition_date.month,
                    "schedule_version_token": "v2",
                    "recognition_method": "straight_line",
                    "base_amount_contract_currency": Decimal("120.000000"),
                    "fx_rate_used": Decimal("1.000000"),
                    "recognized_amount_reporting_currency": Decimal("120.000000"),
                    "cumulative_recognized_reporting_currency": Decimal(str(period_seq * 120)),
                    "schedule_status": "regenerated",
                    "source_contract_reference": contract.source_contract_reference,
                    "parent_reference_id": contract.id,
                    "source_reference_id": line_item.id,
                    "correlation_id": correlation_id,
                },
            )
        )

    await AuditWriter.insert_financial_record(
        async_session,
        model_class=RevenueAdjustment,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(run.id),
            "contract_id": str(contract.id),
            "effective_date": "2026-02-01",
            "idempotency_key": "idem-rev-effective",
        },
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "effective_date": date(2026, 2, 1),
            "adjustment_type": "contract_modification",
            "adjustment_reason": "effective token swap",
            "idempotency_key": "idem-rev-effective",
            "prior_schedule_version_token": "root",
            "new_schedule_version_token": "v2",
            "prior_schedule_reference": str(root_rows[-1].id),
            "new_schedule_reference": str(effective_rows[0].id),
            "catch_up_amount_reporting_currency": Decimal("0.000000"),
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": contract.id,
            "source_reference_id": root_rows[-1].id,
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
            select(RevenueJournalEntry).where(
                RevenueJournalEntry.tenant_id == test_tenant.id,
                RevenueJournalEntry.run_id == run.id,
            )
        )
    ).scalars().all()
    assert len(journal_rows) == 2

    effective_schedule_ids = {row.id for row in effective_rows}
    root_schedule_ids = {row.id for row in root_rows}
    assert {row.schedule_id for row in journal_rows} == effective_schedule_ids
    assert all(row.schedule_id not in root_schedule_ids for row in journal_rows)
