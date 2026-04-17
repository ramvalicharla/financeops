from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.db.append_only import APPEND_ONLY_TABLES
from tests.integration.ratio_variance_phase1f4_helpers import (
    build_ratio_variance_service,
    ensure_tenant_context,
    seed_active_definition_set,
    seed_finalized_normalization_pair,
)


async def _seed_executed_run(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, str]:
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
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    return executed


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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_metric_definitions(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        await ensure_tenant_context(session, tenant_id)
        await seed_active_definition_set(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            effective_from=date(2026, 1, 1),
        )
        definition_id = (
            await session.execute(text("SELECT id FROM metric_definitions LIMIT 1"))
        ).scalar_one()
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE metric_definitions SET definition_name='changed' WHERE id=:id"),
                {"id": str(definition_id)},
            )
            await session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_metric_runs(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        executed = await _seed_executed_run(session, tenant_id=tenant_id)
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE metric_runs SET status='failed' WHERE id=:id"),
                {"id": executed["run_id"]},
            )
            await session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_metric_results(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        executed = await _seed_executed_run(session, tenant_id=tenant_id)
        result_id = (
            await session.execute(
                text("SELECT id FROM metric_results WHERE run_id=:run_id LIMIT 1"),
                {"run_id": executed["run_id"]},
            )
        ).scalar_one()
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE metric_results SET metric_value=0 WHERE id=:id"),
                {"id": str(result_id)},
            )
            await session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_variance_and_trend_and_evidence(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        executed = await _seed_executed_run(session, tenant_id=tenant_id)
        variance_id = (
            await session.execute(
                text("SELECT id FROM variance_results WHERE run_id=:run_id LIMIT 1"),
                {"run_id": executed["run_id"]},
            )
        ).scalar_one()
        trend_id = (
            await session.execute(
                text("SELECT id FROM trend_results WHERE run_id=:run_id LIMIT 1"),
                {"run_id": executed["run_id"]},
            )
        ).scalar_one()
        evidence_id = (
            await session.execute(
                text("SELECT id FROM metric_evidence_links WHERE run_id=:run_id LIMIT 1"),
                {"run_id": executed["run_id"]},
            )
        ).scalar_one()

        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE variance_results SET variance_abs=0 WHERE id=:id"),
                {"id": str(variance_id)},
            )
            await session.flush()
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE trend_results SET trend_value=0 WHERE id=:id"),
                {"id": str(trend_id)},
            )
            await session.flush()
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE metric_evidence_links SET evidence_label='x' WHERE id=:id"),
                {"id": str(evidence_id)},
            )
            await session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_ratio_tables() -> None:
    required = {
        "metric_definitions",
        "metric_definition_components",
        "variance_definitions",
        "trend_definitions",
        "materiality_rules",
        "metric_runs",
        "metric_results",
        "variance_results",
        "trend_results",
        "metric_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
