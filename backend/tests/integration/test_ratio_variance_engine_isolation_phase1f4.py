from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.ratio_variance_phase1f4_helpers import (
    build_ratio_variance_service,
    ensure_tenant_context,
    seed_active_definition_set,
    seed_finalized_normalization_pair,
)


async def _local_ratio_session(ratio_phase1f4_db_url: str):
    engine = create_async_engine(ratio_phase1f4_db_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.begin()
            yield session
            await session.rollback()
    finally:
        await engine.dispose()

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

RECON_TABLES = (
    "reconciliation_sessions",
    "reconciliation_lines",
    "reconciliation_exceptions",
    "reconciliation_resolution_events",
    "reconciliation_evidence_links",
)

FX_TABLES = (
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
)


async def _counts(session: AsyncSession, tables: tuple[str, ...]) -> dict[str, int]:
    data: dict[str, int] = {}
    for table in tables:
        count = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
        data[table] = int(count)
    return data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ratio_run_does_not_modify_engine_or_journal_tables(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        await ensure_tenant_context(session, tenant_id)
        before_engine = await _counts(session, ENGINE_TABLES)
        before_journal = await _counts(session, JOURNAL_TABLES)

        pair = await seed_finalized_normalization_pair(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            reporting_period=date(2026, 1, 31),
        )
        await seed_active_definition_set(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            effective_from=date(2026, 1, 1),
        )
        service = build_ratio_variance_service(session)
        created = await service.create_run(
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            reporting_period=date(2026, 1, 31),
            scope_json={"entity": "LE1"},
            mis_snapshot_id=None,
            payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
            gl_run_id=uuid.UUID(pair["gl_run_id"]),
            reconciliation_session_id=None,
            payroll_gl_reconciliation_run_id=None,
            created_by=tenant_id,
        )
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )

        after_engine = await _counts(session, ENGINE_TABLES)
        after_journal = await _counts(session, JOURNAL_TABLES)
        assert before_engine == after_engine
        assert before_journal == after_journal


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ratio_run_does_not_mutate_normalization_or_reconciliation_tables(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        await ensure_tenant_context(session, tenant_id)
        pair = await seed_finalized_normalization_pair(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            reporting_period=date(2026, 1, 31),
        )
        await seed_active_definition_set(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            effective_from=date(2026, 1, 1),
        )
        before_recon = await _counts(session, RECON_TABLES)
        before_norm = await _counts(
            session,
            (
                "normalization_runs",
                "payroll_normalized_lines",
                "gl_normalized_lines",
                "normalization_exceptions",
                "normalization_evidence_links",
            ),
        )
        service = build_ratio_variance_service(session)
        created = await service.create_run(
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            reporting_period=date(2026, 1, 31),
            scope_json={"entity": "LE1"},
            mis_snapshot_id=None,
            payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
            gl_run_id=uuid.UUID(pair["gl_run_id"]),
            reconciliation_session_id=None,
            payroll_gl_reconciliation_run_id=None,
            created_by=tenant_id,
        )
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )

        after_recon = await _counts(session, RECON_TABLES)
        after_norm = await _counts(
            session,
            (
                "normalization_runs",
                "payroll_normalized_lines",
                "gl_normalized_lines",
                "normalization_exceptions",
                "normalization_evidence_links",
            ),
        )
        assert before_recon == after_recon
        assert before_norm == after_norm


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ratio_run_does_not_invoke_fx_tables(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        await ensure_tenant_context(session, tenant_id)
        before_fx = await _counts(session, FX_TABLES)

        pair = await seed_finalized_normalization_pair(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            reporting_period=date(2026, 1, 31),
        )
        await seed_active_definition_set(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            effective_from=date(2026, 1, 1),
        )
        service = build_ratio_variance_service(session)
        created = await service.create_run(
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            reporting_period=date(2026, 1, 31),
            scope_json={"entity": "LE1"},
            mis_snapshot_id=None,
            payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
            gl_run_id=uuid.UUID(pair["gl_run_id"]),
            reconciliation_session_id=None,
            payroll_gl_reconciliation_run_id=None,
            created_by=tenant_id,
        )
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )

        after_fx = await _counts(session, FX_TABLES)
        assert before_fx == after_fx
