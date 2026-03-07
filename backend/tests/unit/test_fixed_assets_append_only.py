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
from financeops.db.models.fixed_assets import (
    Asset,
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
    AssetJournalEntry,
    FarRun,
    FarRunEvent,
)
from financeops.services.audit_writer import AuditWriter

SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


async def _seed_run(session: AsyncSession, tenant_id: UUID) -> FarRun:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=FarRun,
        tenant_id=tenant_id,
        record_data={"request_signature": f"far-run-{uuid.uuid4()}", "workflow_id": "wf-far-seed"},
        values={
            "request_signature": f"far-run-{uuid.uuid4()}",
            "initiated_by": tenant_id,
            "configuration_json": {"assets": []},
            "workflow_id": "wf-far-seed",
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_asset(session: AsyncSession, tenant_id: UUID) -> Asset:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=Asset,
        tenant_id=tenant_id,
        record_data={"asset_code": f"FAR-{uuid.uuid4()}", "source_acquisition_reference": "SRC-FAR-APPEND"},
        values={
            "asset_code": f"FAR-{uuid.uuid4()}",
            "description": "append-only-asset",
            "entity_id": "ENT-APP",
            "asset_class": "equipment",
            "asset_currency": "USD",
            "reporting_currency": "USD",
            "capitalization_date": date(2026, 1, 1),
            "in_service_date": date(2026, 1, 1),
            "capitalized_amount_asset_currency": Decimal("1000.000000"),
            "depreciation_method": "straight_line",
            "useful_life_months": 12,
            "reducing_balance_rate_annual": None,
            "residual_value_reporting_currency": Decimal("0.000000"),
            "rate_mode": "month_end_locked",
            "source_acquisition_reference": "SRC-FAR-APPEND",
            "parent_reference_id": None,
            "source_reference_id": tenant_id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_far_runs(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_run(session, tenant_id)


async def _seed_far_run_events(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=FarRunEvent,
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


async def _seed_assets(session: AsyncSession, tenant_id: UUID) -> None:
    await _seed_asset(session, tenant_id)


async def _seed_schedule(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    asset = await _seed_asset(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=AssetDepreciationSchedule,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "period_seq": 1,
            "depreciation_date": "2026-01-31",
            "schedule_version_token": "tok-far-append",
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "period_seq": 1,
            "depreciation_date": date(2026, 1, 31),
            "depreciation_period_year": 2026,
            "depreciation_period_month": 1,
            "schedule_version_token": "tok-far-append",
            "opening_carrying_amount_reporting_currency": Decimal("1000.000000"),
            "depreciation_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_depreciation_reporting_currency": Decimal("100.000000"),
            "closing_carrying_amount_reporting_currency": Decimal("900.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 1, 31),
            "fx_rate_source": "same_currency",
            "schedule_status": "scheduled",
            "source_acquisition_reference": asset.source_acquisition_reference,
            "parent_reference_id": asset.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


async def _seed_impairment(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    asset = await _seed_asset(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=AssetImpairment,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "impairment_date": "2026-02-01",
            "idempotency_key": "imp-append",
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "impairment_date": date(2026, 2, 1),
            "impairment_amount_reporting_currency": Decimal("25.000000"),
            "idempotency_key": "imp-append",
            "prior_schedule_version_token": "tok-old",
            "new_schedule_version_token": "tok-new",
            "reason": "append-only-test",
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 2, 1),
            "fx_rate_source": "same_currency",
            "source_acquisition_reference": asset.source_acquisition_reference,
            "parent_reference_id": asset.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_disposal(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    asset = await _seed_asset(session, tenant_id)
    await AuditWriter.insert_financial_record(
        session,
        model_class=AssetDisposal,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "disposal_date": "2026-03-01",
            "idempotency_key": "disp-append",
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "disposal_date": date(2026, 3, 1),
            "proceeds_reporting_currency": Decimal("800.000000"),
            "disposal_cost_reporting_currency": Decimal("5.000000"),
            "carrying_amount_reporting_currency": Decimal("790.000000"),
            "gain_loss_reporting_currency": Decimal("5.000000"),
            "idempotency_key": "disp-append",
            "prior_schedule_version_token": "tok-old",
            "new_schedule_version_token": "tok-new",
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 3, 1),
            "fx_rate_source": "same_currency",
            "source_acquisition_reference": asset.source_acquisition_reference,
            "parent_reference_id": asset.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
            "supersedes_id": None,
        },
    )


async def _seed_journal(session: AsyncSession, tenant_id: UUID) -> None:
    run = await _seed_run(session, tenant_id)
    asset = await _seed_asset(session, tenant_id)
    schedule = await AuditWriter.insert_financial_record(
        session,
        model_class=AssetDepreciationSchedule,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "asset_id": str(asset.id),
            "period_seq": 1,
            "depreciation_date": "2026-01-31",
            "schedule_version_token": "tok-far-journal",
        },
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "period_seq": 1,
            "depreciation_date": date(2026, 1, 31),
            "depreciation_period_year": 2026,
            "depreciation_period_month": 1,
            "schedule_version_token": "tok-far-journal",
            "opening_carrying_amount_reporting_currency": Decimal("1000.000000"),
            "depreciation_amount_reporting_currency": Decimal("100.000000"),
            "cumulative_depreciation_reporting_currency": Decimal("100.000000"),
            "closing_carrying_amount_reporting_currency": Decimal("900.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "fx_rate_date": date(2026, 1, 31),
            "fx_rate_source": "same_currency",
            "schedule_status": "scheduled",
            "source_acquisition_reference": asset.source_acquisition_reference,
            "parent_reference_id": asset.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=AssetJournalEntry,
        tenant_id=tenant_id,
        record_data={"run_id": str(run.id), "journal_reference": "FAR-JRN-APPEND", "line_seq": 1},
        values={
            "run_id": run.id,
            "asset_id": asset.id,
            "depreciation_schedule_id": schedule.id,
            "impairment_id": None,
            "disposal_id": None,
            "journal_reference": "FAR-JRN-APPEND",
            "line_seq": 1,
            "entry_date": date(2026, 1, 31),
            "debit_account": "Depreciation Expense",
            "credit_account": "Accumulated Depreciation",
            "amount_reporting_currency": Decimal("100.000000"),
            "source_acquisition_reference": asset.source_acquisition_reference,
            "parent_reference_id": schedule.id,
            "source_reference_id": asset.source_reference_id,
            "correlation_id": str(uuid.uuid4()),
        },
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str, str], ...] = (
    ("far_runs", _seed_far_runs, "UPDATE far_runs SET workflow_id='mutated'", "DELETE FROM far_runs"),
    (
        "far_run_events",
        _seed_far_run_events,
        "UPDATE far_run_events SET event_type='failed'",
        "DELETE FROM far_run_events",
    ),
    ("assets", _seed_assets, "UPDATE assets SET description='mutated'", "DELETE FROM assets"),
    (
        "asset_depreciation_schedule",
        _seed_schedule,
        "UPDATE asset_depreciation_schedule SET schedule_status='mutated'",
        "DELETE FROM asset_depreciation_schedule",
    ),
    (
        "asset_impairments",
        _seed_impairment,
        "UPDATE asset_impairments SET reason='mutated'",
        "DELETE FROM asset_impairments",
    ),
    (
        "asset_disposals",
        _seed_disposal,
        "UPDATE asset_disposals SET idempotency_key='mutated'",
        "DELETE FROM asset_disposals",
    ),
    (
        "asset_journal_entries",
        _seed_journal,
        "UPDATE asset_journal_entries SET debit_account='mutated'",
        "DELETE FROM asset_journal_entries",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql", "delete_sql"), TABLE_CASES)
async def test_fixed_assets_append_only_blocks_update(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
    delete_sql: str,
) -> None:
    del delete_sql
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(update_sql))


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql", "delete_sql"), TABLE_CASES)
async def test_fixed_assets_append_only_blocks_delete(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
    delete_sql: str,
) -> None:
    del update_sql
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(delete_sql))
