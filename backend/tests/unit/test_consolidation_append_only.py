from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)
from financeops.db.models.consolidation import (
    ConsolidationResult,
    ConsolidationRun,
    ConsolidationRunEvent,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditWriter

SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


async def _seed_snapshot(session: AsyncSession, tenant_id: UUID) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(tenant_id),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "append-snapshot",
        },
        values={
            "entity_id": tenant_id,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "append-snapshot",
            "supersedes_snapshot_id": None,
            "correlation_id": "corr-append-snapshot",
        },
    )


async def _seed_snapshot_line(session: AsyncSession, tenant_id: UUID) -> None:
    snapshot = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(tenant_id),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "append-line-snapshot",
        },
        values={
            "entity_id": tenant_id,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "append-line-snapshot",
            "supersedes_snapshot_id": None,
            "correlation_id": "corr-append-line-snapshot",
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot.id),
            "account_code": "4000",
            "local_amount": "10.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot.id,
            "account_code": "4000",
            "local_amount": Decimal("10.000000"),
            "currency": "USD",
            "ic_reference": None,
            "counterparty_entity": None,
            "transaction_date": None,
            "ic_account_class": None,
            "correlation_id": "corr-append-line",
        },
    )


async def _seed_run(session: AsyncSession, tenant_id: UUID) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "request_signature": "sig-append-run",
            "workflow_id": "wf-append-run",
        },
        values={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "initiated_by": tenant_id,
            "request_signature": "sig-append-run",
            "configuration_json": {"rate_mode": "daily", "entity_snapshots": [], "tolerances": {}},
            "workflow_id": "wf-append-run",
            "correlation_id": "corr-append-run",
        },
    )


async def _seed_run_event(session: AsyncSession, tenant_id: UUID) -> None:
    run = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "request_signature": "sig-append-event",
            "workflow_id": "wf-append-event",
        },
        values={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "initiated_by": tenant_id,
            "request_signature": "sig-append-event",
            "configuration_json": {"rate_mode": "daily", "entity_snapshots": [], "tolerances": {}},
            "workflow_id": "wf-append-event",
            "correlation_id": "corr-append-event",
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRunEvent,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "event_seq": 1,
            "event_type": "accepted",
            "idempotency_key": "seed",
        },
        values={
            "run_id": run.id,
            "event_seq": 1,
            "event_type": "accepted",
            "event_time": datetime.now(UTC),
            "idempotency_key": "seed",
            "metadata_json": None,
            "correlation_id": "corr-append-event-row",
        },
    )


async def _seed_result(session: AsyncSession, tenant_id: UUID) -> None:
    run = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "request_signature": "sig-append-result",
            "workflow_id": "wf-append-result",
        },
        values={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "initiated_by": tenant_id,
            "request_signature": "sig-append-result",
            "configuration_json": {"rate_mode": "daily", "entity_snapshots": [], "tolerances": {}},
            "workflow_id": "wf-append-result",
            "correlation_id": "corr-append-result",
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationResult,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "consolidated_account_code": "4000",
            "consolidated_amount_parent": "10.000000",
            "fx_impact_total": "0.100000",
        },
        values={
            "run_id": run.id,
            "consolidated_account_code": "4000",
            "consolidated_amount_parent": Decimal("10.000000"),
            "fx_impact_total": Decimal("0.100000"),
            "correlation_id": "corr-append-result-row",
        },
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str], ...] = (
    (
        "normalized_financial_snapshots",
        _seed_snapshot,
        "UPDATE normalized_financial_snapshots SET produced_by_module='mutated'",
    ),
    (
        "normalized_financial_snapshot_lines",
        _seed_snapshot_line,
        "UPDATE normalized_financial_snapshot_lines SET account_code='9999'",
    ),
    (
        "consolidation_runs",
        _seed_run,
        "UPDATE consolidation_runs SET parent_currency='EUR'",
    ),
    (
        "consolidation_run_events",
        _seed_run_event,
        "UPDATE consolidation_run_events SET event_type='failed'",
    ),
    (
        "consolidation_results",
        _seed_result,
        "UPDATE consolidation_results SET fx_impact_total=999",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_consolidation_append_only_blocks_update(
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
async def test_consolidation_append_only_blocks_delete(
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
