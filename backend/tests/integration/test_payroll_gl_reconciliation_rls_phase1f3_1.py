from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    PAYROLL_GL_RECON_TABLES,
    build_payroll_gl_reconciliation_service,
    ensure_tenant_context,
    seed_finalized_normalization_pair,
    seed_mapping_and_rule,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_paygl_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_paygl_probe_user"))
    for table_name in (
        "payroll_gl_reconciliation_mappings",
        "payroll_gl_reconciliation_runs",
        "reconciliation_lines",
    ):
        await session.execute(
            text(f"GRANT SELECT, INSERT ON {table_name} TO rls_paygl_probe_user")
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
    return {
        "run_id": executed["run_id"],
        "session_id": executed["reconciliation_session_id"],
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_mapping(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _configure_probe_role(payroll_gl_recon_phase1f3_1_session)
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    await payroll_gl_recon_phase1f3_1_session.execute(text("SET ROLE rls_paygl_probe_user"))
    try:
        await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
        visible = (
            await payroll_gl_recon_phase1f3_1_session.execute(
                text("SELECT COUNT(*) FROM payroll_gl_reconciliation_mappings")
            )
        ).scalar_one()
        assert visible >= 1
    finally:
        if payroll_gl_recon_phase1f3_1_session.in_transaction():
            await payroll_gl_recon_phase1f3_1_session.rollback()
        await payroll_gl_recon_phase1f3_1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_mapping(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(payroll_gl_recon_phase1f3_1_session)
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_b)
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=tenant_b,
        effective_from=date(2026, 1, 1),
    )
    await payroll_gl_recon_phase1f3_1_session.execute(text("SET ROLE rls_paygl_probe_user"))
    try:
        await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_a)
        visible = (
            await payroll_gl_recon_phase1f3_1_session.execute(
                text("SELECT COUNT(*) FROM payroll_gl_reconciliation_mappings")
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if payroll_gl_recon_phase1f3_1_session.in_transaction():
            await payroll_gl_recon_phase1f3_1_session.rollback()
        await payroll_gl_recon_phase1f3_1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_run(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(payroll_gl_recon_phase1f3_1_session)
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_a)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    created = await service.create_run(
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_a,
    )
    await payroll_gl_recon_phase1f3_1_session.execute(text("SET ROLE rls_paygl_probe_user"))
    try:
        await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_a)
        with pytest.raises(DBAPIError):
            await payroll_gl_recon_phase1f3_1_session.execute(
                text(
                    """
                    INSERT INTO payroll_gl_reconciliation_runs
                      (id, tenant_id, chain_hash, previous_hash, organisation_id,
                       reconciliation_session_id, payroll_run_id, gl_run_id,
                       mapping_version_token, rule_version_token, reporting_period,
                       run_token, status, created_by)
                    VALUES
                      (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                       :session_id, :payroll_run_id, :gl_run_id,
                       :mapping_version_token, :rule_version_token, :reporting_period,
                       :run_token, :status, :created_by)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(tenant_b),
                    "chain_hash": "1" * 64,
                    "previous_hash": "0" * 64,
                    "organisation_id": str(tenant_b),
                    "session_id": created["reconciliation_session_id"],
                    "payroll_run_id": pair["payroll_run_id"],
                    "gl_run_id": pair["gl_run_id"],
                    "mapping_version_token": "a" * 64,
                    "rule_version_token": "b" * 64,
                    "reporting_period": date(2026, 1, 31),
                    "run_token": "c" * 64,
                    "status": "created",
                    "created_by": str(tenant_b),
                },
            )
            await payroll_gl_recon_phase1f3_1_session.flush()
    finally:
        if payroll_gl_recon_phase1f3_1_session.in_transaction():
            await payroll_gl_recon_phase1f3_1_session.rollback()
        await payroll_gl_recon_phase1f3_1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_reconciliation_lines(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(payroll_gl_recon_phase1f3_1_session)
    run_b = await _seed_executed_run(payroll_gl_recon_phase1f3_1_session, tenant_id=tenant_b)
    await payroll_gl_recon_phase1f3_1_session.execute(text("SET ROLE rls_paygl_probe_user"))
    try:
        await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_a)
        visible = (
            await payroll_gl_recon_phase1f3_1_session.execute(
                text("SELECT COUNT(*) FROM reconciliation_lines WHERE session_id=:session_id"),
                {"session_id": run_b["session_id"]},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if payroll_gl_recon_phase1f3_1_session.in_transaction():
            await payroll_gl_recon_phase1f3_1_session.rollback()
        await payroll_gl_recon_phase1f3_1_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_payroll_gl_reconciliation_tables(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    for table_name in PAYROLL_GL_RECON_TABLES:
        row = (
            await payroll_gl_recon_phase1f3_1_session.execute(
                text(
                    """
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = :table_name
                    """
                ),
                {"table_name": table_name},
            )
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True
