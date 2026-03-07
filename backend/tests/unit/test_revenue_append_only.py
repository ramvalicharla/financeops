from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.revenue import (
    RevenueAdjustment,
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueRunEvent,
    RevenueSchedule,
)
from financeops.services.audit_writer import AuditWriter

SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


async def _seed_run(session: AsyncSession, tenant_id: UUID) -> RevenueRun:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueRun,
        tenant_id=tenant_id,
        record_data={"request_signature": f"rev-run-{uuid.uuid4()}", "workflow_id": "wf-rev-seed"},
        values={
            "request_signature": f"rev-run-{uuid.uuid4()}",
            "initiated_by": tenant_id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "contracts": []},
            "workflow_id": "wf-rev-seed",
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_contract_graph(session: AsyncSession, tenant_id: UUID) -> tuple[RevenueContract, RevenuePerformanceObligation, RevenueContractLineItem]:
    correlation_id = str(uuid.uuid4())
    contract = await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueContract,
        tenant_id=tenant_id,
        record_data={"contract_number": f"REV-{uuid.uuid4()}"},
        values={
            "contract_number": f"REV-{uuid.uuid4()}",
            "customer_id": "CUST-APPEND",
            "contract_currency": "USD",
            "contract_start_date": date(2026, 1, 1),
            "contract_end_date": date(2026, 12, 31),
            "total_contract_value": Decimal("100.000000"),
            "source_contract_reference": "SRC-APPEND",
            "policy_code": "ASC606",
            "policy_version": "v1",
            "correlation_id": correlation_id,
            "supersedes_id": None,
        },
    )
    obligation = await AuditWriter.insert_financial_record(
        session,
        model_class=RevenuePerformanceObligation,
        tenant_id=tenant_id,
        record_data={"contract_id": str(contract.id), "obligation_code": "OBL-APPEND"},
        values={
            "contract_id": contract.id,
            "obligation_code": "OBL-APPEND",
            "description": "Append obligation",
            "standalone_selling_price": Decimal("100.000000"),
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
        session,
        model_class=RevenueContractLineItem,
        tenant_id=tenant_id,
        record_data={"contract_id": str(contract.id), "line_code": "LINE-APPEND"},
        values={
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "line_code": "LINE-APPEND",
            "line_amount": Decimal("100.000000"),
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
    return contract, obligation, line_item


async def _seed_revenue_runs(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_run(session, tenant_id)


async def _seed_revenue_run_events(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueRunEvent,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "event_seq": 1, "event_type": "accepted"},
        values={
            "run_id": run.id,
            "event_seq": 1,
            "event_type": "accepted",
            "event_time": datetime.now(UTC),
            "idempotency_key": f"seed-{uuid.uuid4()}",
            "metadata_json": None,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_revenue_contracts(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_contract_graph(session, tenant_id)


async def _seed_revenue_schedules(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    contract, obligation, line_item = await _seed_contract_graph(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueSchedule,
        tenant_id=tenant_id,
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
            "base_amount_contract_currency": Decimal("100.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "recognized_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_recognized_reporting_currency": Decimal("100.000000"),
            "schedule_status": "recognized",
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": obligation.id,
            "source_reference_id": line_item.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_revenue_journal_entries(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    contract, obligation, line_item = await _seed_contract_graph(session, tenant_id)
    schedule = await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueSchedule,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "contract_line_item_id": str(line_item.id)},
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "contract_line_item_id": line_item.id,
            "period_seq": 2,
            "recognition_date": date(2026, 3, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 3,
            "schedule_version_token": "root-v2",
            "recognition_method": "straight_line",
            "base_amount_contract_currency": Decimal("100.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "recognized_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_recognized_reporting_currency": Decimal("100.000000"),
            "schedule_status": "recognized",
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": obligation.id,
            "source_reference_id": line_item.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueJournalEntry,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "schedule_id": str(schedule.id)},
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "obligation_id": obligation.id,
            "schedule_id": schedule.id,
            "journal_reference": f"REV-{uuid.uuid4()}",
            "entry_date": date(2026, 3, 31),
            "debit_account": "Accounts Receivable",
            "credit_account": "Revenue",
            "amount_reporting_currency": Decimal("100.000000"),
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": schedule.id,
            "source_reference_id": line_item.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_revenue_adjustments(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    contract, _obligation, _line_item = await _seed_contract_graph(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=RevenueAdjustment,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "contract_id": str(contract.id)},
        values={
            "run_id": run.id,
            "contract_id": contract.id,
            "effective_date": date(2026, 6, 30),
            "adjustment_type": "contract_modification",
            "adjustment_reason": "append-only-test",
            "idempotency_key": f"idem-{uuid.uuid4()}",
            "prior_schedule_version_token": "root",
            "new_schedule_version_token": "root-v2",
            "prior_schedule_reference": None,
            "new_schedule_reference": "forward_regenerated",
            "catch_up_amount_reporting_currency": Decimal("0.000000"),
            "source_contract_reference": contract.source_contract_reference,
            "parent_reference_id": contract.id,
            "source_reference_id": contract.id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str], ...] = (
    ("revenue_runs", _seed_revenue_runs, "UPDATE revenue_runs SET workflow_id='mutated'"),
    (
        "revenue_run_events",
        _seed_revenue_run_events,
        "UPDATE revenue_run_events SET event_type='failed'",
    ),
    (
        "revenue_contracts",
        _seed_revenue_contracts,
        "UPDATE revenue_contracts SET customer_id='MUTATED'",
    ),
    (
        "revenue_schedules",
        _seed_revenue_schedules,
        "UPDATE revenue_schedules SET schedule_status='mutated'",
    ),
    (
        "revenue_journal_entries",
        _seed_revenue_journal_entries,
        "UPDATE revenue_journal_entries SET debit_account='Mutated'",
    ),
    (
        "revenue_adjustments",
        _seed_revenue_adjustments,
        "UPDATE revenue_adjustments SET adjustment_reason='mutated'",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_revenue_append_only_blocks_update(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
) -> None:
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(update_sql))


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_revenue_append_only_blocks_delete(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
) -> None:
    del update_sql
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(f"DELETE FROM {table_name}"))
