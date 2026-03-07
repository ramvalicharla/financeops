from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    build_payroll_gl_reconciliation_service,
    ensure_tenant_context,
    seed_finalized_normalization_pair,
    seed_mapping_and_rule,
)

ENGINE_TABLES = (
    "revenue_schedules",
    "lease_liability_schedule",
    "prepaid_amortization_schedule",
    "asset_depreciation_schedule",
)

JOURNAL_TABLES = (
    "revenue_journal_entries",
    "lease_journal_entries",
    "prepaid_journal_entries",
    "asset_journal_entries",
)

NORMALIZATION_OUTPUT_TABLES = (
    "normalization_runs",
    "payroll_normalized_lines",
    "gl_normalized_lines",
    "normalization_exceptions",
    "normalization_evidence_links",
)

FX_TABLES = (
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
)


async def _table_counts(session: AsyncSession, table_names: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        count = (await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))).scalar_one()
        counts[table_name] = int(count)
    return counts


async def _run_payroll_gl_reconciliation(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict[str, str]:
    await ensure_tenant_context(session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    return executed


@pytest.mark.asyncio
@pytest.mark.integration
async def test_payroll_gl_reconciliation_does_not_modify_accounting_engine_tables(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    before_engine = await _table_counts(payroll_gl_recon_phase1f3_1_session, ENGINE_TABLES)
    before_journals = await _table_counts(payroll_gl_recon_phase1f3_1_session, JOURNAL_TABLES)
    await _run_payroll_gl_reconciliation(payroll_gl_recon_phase1f3_1_session, tenant_id=tenant_id)
    after_engine = await _table_counts(payroll_gl_recon_phase1f3_1_session, ENGINE_TABLES)
    after_journals = await _table_counts(payroll_gl_recon_phase1f3_1_session, JOURNAL_TABLES)
    assert before_engine == after_engine
    assert before_journals == after_journals


@pytest.mark.asyncio
@pytest.mark.integration
async def test_payroll_gl_reconciliation_does_not_mutate_normalization_outputs(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    before_norm = await _table_counts(
        payroll_gl_recon_phase1f3_1_session, NORMALIZATION_OUTPUT_TABLES
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    after_norm = await _table_counts(
        payroll_gl_recon_phase1f3_1_session, NORMALIZATION_OUTPUT_TABLES
    )
    assert before_norm == after_norm


@pytest.mark.asyncio
@pytest.mark.integration
async def test_payroll_gl_reconciliation_does_not_invoke_fx_tables(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    before_fx = await _table_counts(payroll_gl_recon_phase1f3_1_session, FX_TABLES)
    await _run_payroll_gl_reconciliation(payroll_gl_recon_phase1f3_1_session, tenant_id=tenant_id)
    after_fx = await _table_counts(payroll_gl_recon_phase1f3_1_session, FX_TABLES)
    assert before_fx == after_fx

