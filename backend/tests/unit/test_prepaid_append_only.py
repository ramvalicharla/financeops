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
from financeops.db.models.prepaid import (
    Prepaid,
    PrepaidAdjustment,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
    PrepaidRun,
    PrepaidRunEvent,
)
from financeops.services.audit_writer import AuditWriter

SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


async def _seed_run(session: AsyncSession, tenant_id: UUID) -> PrepaidRun:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidRun,
        tenant_id=tenant_id,
        record_data={"request_signature": f"ppd-run-{uuid.uuid4()}", "workflow_id": "wf-ppd-seed"},
        values={
            "request_signature": f"ppd-run-{uuid.uuid4()}",
            "initiated_by": tenant_id,
            "configuration_json": {"prepaids": []},
            "workflow_id": "wf-ppd-seed",
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_prepaid(session: AsyncSession, tenant_id: UUID) -> Prepaid:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=Prepaid,
        tenant_id=tenant_id,
        record_data={"prepaid_code": f"PPD-{uuid.uuid4()}", "source_expense_reference": "SRC-PPD-APPEND"},
        values={
            "prepaid_code": f"PPD-{uuid.uuid4()}",
            "description": "append-only-prepaid",
            "prepaid_currency": "USD",
            "reporting_currency": "USD",
            "term_start_date": date(2026, 1, 1),
            "term_end_date": date(2026, 3, 31),
            "base_amount_contract_currency": Decimal("300.000000"),
            "period_frequency": "monthly",
            "pattern_type": "straight_line",
            "pattern_json_normalized": {"pattern_type": "straight_line", "periods": []},
            "rate_mode": "month_end_locked",
            "source_expense_reference": "SRC-PPD-APPEND",
            "parent_reference_id": None,
            "source_reference_id": tenant_id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_prepaid_runs(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_run(session, tenant_id)


async def _seed_prepaid_run_events(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidRunEvent,
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


async def _seed_prepaids(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_prepaid(session, tenant_id)


async def _seed_prepaid_schedule(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    prepaid = await _seed_prepaid(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidAmortizationSchedule,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "period_seq": 1,
            "amortization_date": "2026-01-31",
            "schedule_version_token": "tok-append",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "period_seq": 1,
            "amortization_date": date(2026, 1, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 1,
            "schedule_version_token": "tok-append",
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
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_prepaid_journal(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    prepaid = await _seed_prepaid(session, tenant_id)
    schedule = await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidAmortizationSchedule,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "period_seq": 1,
            "amortization_date": "2026-01-31",
            "schedule_version_token": "tok-append",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "period_seq": 1,
            "amortization_date": date(2026, 1, 31),
            "recognition_period_year": 2026,
            "recognition_period_month": 1,
            "schedule_version_token": "tok-append",
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
            "correlation_id": str(uuid.uuid4()),
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidJournalEntry,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "schedule_id": str(schedule.id),
            "journal_reference": f"PPD-{uuid.uuid4()}",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "schedule_id": schedule.id,
            "journal_reference": f"PPD-{uuid.uuid4()}",
            "entry_date": date(2026, 1, 31),
            "debit_account": "Prepaid Expense",
            "credit_account": "Prepaid Asset",
            "amount_reporting_currency": Decimal("100.000000"),
            "source_expense_reference": prepaid.source_expense_reference,
            "parent_reference_id": schedule.id,
            "source_reference_id": prepaid.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_prepaid_adjustments(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    prepaid = await _seed_prepaid(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=PrepaidAdjustment,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "prepaid_id": str(prepaid.id),
            "effective_date": "2026-02-01",
            "adjustment_type": "prospective",
            "idempotency_key": "append-test",
        },
        values={
            "run_id": run.id,
            "prepaid_id": prepaid.id,
            "effective_date": date(2026, 2, 1),
            "adjustment_type": "prospective",
            "adjustment_reason": "append-only-test",
            "idempotency_key": "append-test",
            "prior_schedule_version_token": "tok-old",
            "new_schedule_version_token": "tok-new",
            "catch_up_amount_reporting_currency": Decimal("0.000000"),
            "source_expense_reference": prepaid.source_expense_reference,
            "parent_reference_id": prepaid.id,
            "source_reference_id": prepaid.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str], ...] = (
    ("prepaid_runs", _seed_prepaid_runs, "UPDATE prepaid_runs SET workflow_id='mutated'"),
    (
        "prepaid_run_events",
        _seed_prepaid_run_events,
        "UPDATE prepaid_run_events SET event_type='failed'",
    ),
    ("prepaids", _seed_prepaids, "UPDATE prepaids SET description='mutated'"),
    (
        "prepaid_amortization_schedule",
        _seed_prepaid_schedule,
        "UPDATE prepaid_amortization_schedule SET schedule_status='mutated'",
    ),
    (
        "prepaid_journal_entries",
        _seed_prepaid_journal,
        "UPDATE prepaid_journal_entries SET debit_account='mutated'",
    ),
    (
        "prepaid_adjustments",
        _seed_prepaid_adjustments,
        "UPDATE prepaid_adjustments SET adjustment_reason='mutated'",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_prepaid_append_only_blocks_update(
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
async def test_prepaid_append_only_blocks_delete(
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
