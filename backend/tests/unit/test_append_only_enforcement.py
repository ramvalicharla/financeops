from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
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
from financeops.db.models.fx_rates import FxRateFetchRun, FxRateQuote
from financeops.services.audit_writer import AuditWriter
from financeops.services.credit_service import add_credits
from financeops.services.fx.fx_rate_service import (
    compute_and_store_variance,
    create_manual_monthly_rate,
)
from financeops.services.mis_service import create_template
from financeops.services.reconciliation_service import create_gl_entry


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


SeedFn = Callable[[AsyncSession, UUID], Awaitable[None]]


async def _seed_mis_templates(session: AsyncSession, tenant_id: UUID) -> None:
    await create_template(
        session,
        tenant_id=tenant_id,
        name="AppendOnly",
        entity_name="Entity A",
        template_data={"sheets": []},
        created_by=tenant_id,
    )


async def _seed_mis_uploads(session: AsyncSession, tenant_id: UUID) -> None:
    from financeops.services.mis_service import create_upload

    await create_upload(
        session,
        tenant_id=tenant_id,
        entity_name="Entity Upload",
        period_year=2025,
        period_month=12,
        file_name="append_only_upload.xlsx",
        file_hash="a" * 64,
        uploaded_by=tenant_id,
    )


async def _seed_gl_entries(session: AsyncSession, tenant_id: UUID) -> None:
    await create_gl_entry(
        session,
        tenant_id=tenant_id,
        period_year=2025,
        period_month=12,
        entity_name="Entity GL",
        account_code="9000",
        account_name="AppendOnlyAccount",
        debit_amount=Decimal("1.00"),
        credit_amount=Decimal("0.00"),
        uploaded_by=tenant_id,
    )


async def _seed_credit_transactions(session: AsyncSession, tenant_id: UUID) -> None:
    await add_credits(session, tenant_id, Decimal("10.00"), "append_only_test")


async def _seed_fx_rate_fetch_runs(session: AsyncSession, tenant_id: UUID) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=FxRateFetchRun,
        tenant_id=tenant_id,
        record_data={
            "rate_date": date(2026, 3, 6).isoformat(),
            "base_currency": "USD",
            "quote_currency": "INR",
            "status": "success",
        },
        values={
            "rate_date": date(2026, 3, 6),
            "base_currency": "USD",
            "quote_currency": "INR",
            "status": "success",
            "provider_count": 4,
            "success_count": 4,
            "failure_count": 0,
            "selected_rate": Decimal("83.100000"),
            "selected_source": "provider_consensus",
            "selection_method": "median",
            "fallback_used": False,
            "initiated_by": tenant_id,
            "correlation_id": "append-only-fetch",
            "provider_errors": None,
        },
    )


async def _seed_fx_rate_quotes(session: AsyncSession, tenant_id: UUID) -> None:
    run = await AuditWriter.insert_financial_record(
        session,
        model_class=FxRateFetchRun,
        tenant_id=tenant_id,
        record_data={
            "rate_date": date(2026, 3, 6).isoformat(),
            "base_currency": "USD",
            "quote_currency": "INR",
            "status": "success",
        },
        values={
            "rate_date": date(2026, 3, 6),
            "base_currency": "USD",
            "quote_currency": "INR",
            "status": "success",
            "provider_count": 4,
            "success_count": 4,
            "failure_count": 0,
            "selected_rate": Decimal("83.100000"),
            "selected_source": "provider_consensus",
            "selection_method": "median",
            "fallback_used": False,
            "initiated_by": tenant_id,
            "correlation_id": "append-only-quote-run",
            "provider_errors": None,
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=FxRateQuote,
        tenant_id=tenant_id,
        record_data={
            "fetch_run_id": str(run.id),
            "provider_name": "ecb",
            "rate_date": date(2026, 3, 6).isoformat(),
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "83.100000",
        },
        values={
            "fetch_run_id": run.id,
            "provider_name": "ecb",
            "rate_date": date(2026, 3, 6),
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": Decimal("83.100000"),
            "source_timestamp": None,
            "correlation_id": "append-only-quote",
            "raw_payload": {"provider": "ecb"},
        },
    )


async def _seed_fx_manual_monthly_rates(session: AsyncSession, tenant_id: UUID) -> None:
    await create_manual_monthly_rate(
        session,
        tenant_id=tenant_id,
        entered_by=tenant_id,
        correlation_id="append-only-manual",
        period_year=2026,
        period_month=3,
        base_currency="USD",
        quote_currency="INR",
        rate=Decimal("83.100000"),
        reason="append-only manual seed",
        supersedes_rate_id=None,
    )


async def _seed_fx_variance_results(session: AsyncSession, tenant_id: UUID) -> None:
    await compute_and_store_variance(
        session,
        tenant_id=tenant_id,
        computed_by=tenant_id,
        correlation_id="append-only-variance",
        period_year=2026,
        period_month=3,
        base_currency="USD",
        quote_currency="INR",
        expected_difference=Decimal("1000.000000"),
        actual_difference=Decimal("1020.000000"),
        entity_name="Entity A",
        notes="seed",
    )


TABLE_CASES: tuple[tuple[str, SeedFn, str], ...] = (
    ("mis_templates", _seed_mis_templates, "UPDATE mis_templates SET name='Mutated'"),
    ("mis_uploads", _seed_mis_uploads, "UPDATE mis_uploads SET status='processed'"),
    ("gl_entries", _seed_gl_entries, "UPDATE gl_entries SET account_name='Mutated'"),
    (
        "credit_transactions",
        _seed_credit_transactions,
        "UPDATE credit_transactions SET task_type='mutated'",
    ),
    (
        "fx_rate_fetch_runs",
        _seed_fx_rate_fetch_runs,
        "UPDATE fx_rate_fetch_runs SET status='failed'",
    ),
    (
        "fx_rate_quotes",
        _seed_fx_rate_quotes,
        "UPDATE fx_rate_quotes SET provider_name='mutated'",
    ),
    (
        "fx_manual_monthly_rates",
        _seed_fx_manual_monthly_rates,
        "UPDATE fx_manual_monthly_rates SET reason='mutated'",
    ),
    (
        "fx_variance_results",
        _seed_fx_variance_results,
        "UPDATE fx_variance_results SET notes='mutated'",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_append_only_blocks_update(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
):
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(update_sql))


@pytest.mark.asyncio
@pytest.mark.parametrize(("table_name", "seed_fn", "update_sql"), TABLE_CASES)
async def test_append_only_blocks_delete(
    async_session: AsyncSession,
    test_tenant,
    table_name: str,
    seed_fn: SeedFn,
    update_sql: str,
):
    del update_sql  # unused in delete test param tuple
    await seed_fn(async_session, test_tenant.id)
    await _install_append_only_guard(async_session, table_name)

    with pytest.raises(DBAPIError):
        await async_session.execute(text(f"DELETE FROM {table_name}"))
