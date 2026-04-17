from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.ratio_variance_phase1f4_helpers import (
    RATIO_TABLES,
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


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_ratio_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_ratio_probe_user"))
    for table_name in (
        "metric_definitions",
        "metric_runs",
        "metric_results",
    ):
        await session.execute(text(f"GRANT SELECT, INSERT ON {table_name} TO rls_ratio_probe_user"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_metric_definition(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_id = uuid.uuid4()
        await _configure_probe_role(session)
        await ensure_tenant_context(session, tenant_id)
        await seed_active_definition_set(
            session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            created_by=tenant_id,
            effective_from=date(2026, 1, 1),
        )
        await session.execute(text("SET ROLE rls_ratio_probe_user"))
        try:
            await ensure_tenant_context(session, tenant_id)
            count = (
                await session.execute(text("SELECT COUNT(*) FROM metric_definitions"))
            ).scalar_one()
            assert count >= 1
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_metric_definition(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        await _configure_probe_role(session)
        await ensure_tenant_context(session, tenant_b)
        await seed_active_definition_set(
            session,
            tenant_id=tenant_b,
            organisation_id=tenant_b,
            created_by=tenant_b,
            effective_from=date(2026, 1, 1),
        )
        await session.execute(text("SET ROLE rls_ratio_probe_user"))
        try:
            await ensure_tenant_context(session, tenant_a)
            count = (
                await session.execute(text("SELECT COUNT(*) FROM metric_definitions"))
            ).scalar_one()
            assert count == 0
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_run(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        await _configure_probe_role(session)
        await ensure_tenant_context(session, tenant_a)
        pair = await seed_finalized_normalization_pair(
            session,
            tenant_id=tenant_a,
            organisation_id=tenant_a,
            created_by=tenant_a,
            reporting_period=date(2026, 1, 31),
        )
        await seed_active_definition_set(
            session,
            tenant_id=tenant_a,
            organisation_id=tenant_a,
            created_by=tenant_a,
            effective_from=date(2026, 1, 1),
        )
        service = build_ratio_variance_service(session)
        await service.create_run(
            tenant_id=tenant_a,
            organisation_id=tenant_a,
            reporting_period=date(2026, 1, 31),
            scope_json={"entity": "LE1"},
            mis_snapshot_id=None,
            payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
            gl_run_id=uuid.UUID(pair["gl_run_id"]),
            reconciliation_session_id=None,
            payroll_gl_reconciliation_run_id=None,
            created_by=tenant_a,
        )

        await session.execute(text("SET ROLE rls_ratio_probe_user"))
        try:
            await ensure_tenant_context(session, tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        """
                        INSERT INTO metric_runs
                          (id, tenant_id, chain_hash, previous_hash, organisation_id,
                           reporting_period, scope_json, payroll_run_id, gl_run_id,
                           metric_definition_version_token, variance_definition_version_token,
                           trend_definition_version_token, materiality_rule_version_token,
                           input_signature_hash, run_token, status, created_by)
                        VALUES
                          (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                           :reporting_period, '{}'::jsonb, :payroll_run_id, :gl_run_id,
                           :md, :vd, :td, :mr, :sig, :token, 'created', :created_by)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "tenant_id": str(tenant_b),
                        "chain_hash": "1" * 64,
                        "previous_hash": "0" * 64,
                        "organisation_id": str(tenant_b),
                        "reporting_period": date(2026, 1, 31),
                        "payroll_run_id": pair["payroll_run_id"],
                        "gl_run_id": pair["gl_run_id"],
                        "md": "a" * 64,
                        "vd": "b" * 64,
                        "td": "c" * 64,
                        "mr": "d" * 64,
                        "sig": "e" * 64,
                        "token": uuid.uuid4().hex,
                        "created_by": str(tenant_b),
                    },
                )
                await session.flush()
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_ratio_tables(
    ratio_phase1f4_db_url: str,
) -> None:
    async for session in _local_ratio_session(ratio_phase1f4_db_url):
        for table in RATIO_TABLES:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT relrowsecurity, relforcerowsecurity
                        FROM pg_class
                        WHERE relname=:table_name
                        """
                    ),
                    {"table_name": table},
                )
            ).one()
            assert row.relrowsecurity is True
            assert row.relforcerowsecurity is True
