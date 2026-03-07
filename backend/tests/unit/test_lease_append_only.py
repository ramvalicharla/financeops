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
from financeops.db.models.lease import (
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeaseModification,
    LeasePayment,
    LeaseRouSchedule,
    LeaseRun,
    LeaseRunEvent,
)
from financeops.services.audit_writer import AuditWriter

SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


async def _seed_run(session: AsyncSession, tenant_id: UUID) -> LeaseRun:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseRun,
        tenant_id=tenant_id,
        record_data={"request_signature": f"lease-run-{uuid.uuid4()}", "workflow_id": "wf-lease-seed"},
        values={
            "request_signature": f"lease-run-{uuid.uuid4()}",
            "initiated_by": tenant_id,
            "configuration_json": {"reporting_currency": "USD", "rate_mode": "daily", "leases": []},
            "workflow_id": "wf-lease-seed",
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_lease(session: AsyncSession, tenant_id: UUID) -> Lease:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=Lease,
        tenant_id=tenant_id,
        record_data={"lease_number": f"LEASE-{uuid.uuid4()}"},
        values={
            "lease_number": f"LEASE-{uuid.uuid4()}",
            "counterparty_id": "CP-APPEND",
            "lease_currency": "USD",
            "commencement_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "payment_frequency": "monthly",
            "initial_discount_rate": Decimal("0.120000"),
            "discount_rate_source": "policy",
            "discount_rate_reference_date": date(2026, 1, 1),
            "discount_rate_policy_code": "LSE-RATE",
            "initial_measurement_basis": "present_value",
            "source_lease_reference": "SRC-LEASE-APPEND",
            "policy_code": "ASC842",
            "policy_version": "v1",
            "parent_reference_id": None,
            "source_reference_id": None,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_lease_runs(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_run(session, tenant_id)


async def _seed_lease_run_events(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseRunEvent,
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


async def _seed_leases(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_lease(session, tenant_id)


async def _seed_lease_payments(session: AsyncSession, tenant_id: UUID) -> None:
    lease = await _seed_lease(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeasePayment,
        tenant_id=tenant_id,
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
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_lease_liability_schedule(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    lease = await _seed_lease(session, tenant_id)
    payment = await AuditWriter.insert_financial_record(
        session,
        model_class=LeasePayment,
        tenant_id=tenant_id,
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
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=tenant_id,
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
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_lease_rou_schedule(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    lease = await _seed_lease(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseRouSchedule,
        tenant_id=tenant_id,
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
            "source_reference_id": lease.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_lease_modifications(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    lease = await _seed_lease(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseModification,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "effective_date": "2026-06-30"},
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "effective_date": date(2026, 6, 30),
            "modification_type": "term_change",
            "modification_reason": "append-only-test",
            "idempotency_key": f"idem-{uuid.uuid4()}",
            "prior_schedule_version_token": "root",
            "new_schedule_version_token": "root-v2",
            "prior_schedule_reference": None,
            "new_schedule_reference": "forward_regenerated",
            "remeasurement_delta_reporting_currency": Decimal("0.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": lease.id,
            "source_reference_id": lease.id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_lease_journal_entries(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    lease = await _seed_lease(session, tenant_id)
    liability = await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseLiabilitySchedule,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "schedule_date": "2026-01-31"},
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "payment_id": None,
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
            "source_reference_id": lease.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseJournalEntry,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "lease_id": str(lease.id), "journal_reference": f"LSE-{uuid.uuid4()}"},
        values={
            "run_id": run.id,
            "lease_id": lease.id,
            "liability_schedule_id": liability.id,
            "rou_schedule_id": None,
            "journal_reference": f"LSE-{uuid.uuid4()}",
            "entry_date": date(2026, 1, 31),
            "debit_account": "Lease Expense",
            "credit_account": "Lease Liability",
            "amount_reporting_currency": Decimal("1.000000"),
            "source_lease_reference": lease.source_lease_reference,
            "parent_reference_id": liability.id,
            "source_reference_id": lease.id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str], ...] = (
    ("lease_runs", _seed_lease_runs, "UPDATE lease_runs SET workflow_id='mutated'"),
    ("lease_run_events", _seed_lease_run_events, "UPDATE lease_run_events SET event_type='failed'"),
    ("leases", _seed_leases, "UPDATE leases SET counterparty_id='MUTATED'"),
    ("lease_payments", _seed_lease_payments, "UPDATE lease_payments SET payment_type='mutated'"),
    (
        "lease_liability_schedule",
        _seed_lease_liability_schedule,
        "UPDATE lease_liability_schedule SET closing_liability_reporting_currency=999",
    ),
    (
        "lease_rou_schedule",
        _seed_lease_rou_schedule,
        "UPDATE lease_rou_schedule SET closing_rou_reporting_currency=999",
    ),
    (
        "lease_modifications",
        _seed_lease_modifications,
        "UPDATE lease_modifications SET modification_reason='mutated'",
    ),
    (
        "lease_journal_entries",
        _seed_lease_journal_entries,
        "UPDATE lease_journal_entries SET debit_account='Mutated'",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_lease_append_only_blocks_update(
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
async def test_lease_append_only_blocks_delete(
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
