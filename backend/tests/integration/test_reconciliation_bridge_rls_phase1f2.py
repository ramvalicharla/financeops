from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation_bridge import ReconciliationSession
from financeops.services.audit_writer import AuditWriter
from tests.integration.reconciliation_phase1f2_helpers import (
    RECON_TABLES,
    ensure_tenant_context,
    hash64,
    seed_recon_session,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_recon_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_recon_probe_user"))
    for table_name in ("reconciliation_sessions", "reconciliation_lines"):
        await session.execute(
            text(f"GRANT SELECT, INSERT ON {table_name} TO rls_recon_probe_user")
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_reconciliation_session(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    await _configure_probe_role(recon_phase1f2_session)
    await recon_phase1f2_session.execute(text("SET ROLE rls_recon_probe_user"))
    try:
        await ensure_tenant_context(recon_phase1f2_session, tenant_a)
        session_row = await seed_recon_session(
            recon_phase1f2_session,
            tenant_id=tenant_a,
            organisation_id=tenant_a,
            created_by=tenant_a,
            token_seed="rls_own",
        )
        visible = (
            await recon_phase1f2_session.execute(
                text("SELECT COUNT(*) FROM reconciliation_sessions WHERE id = :session_id"),
                {"session_id": str(session_row.id)},
            )
        ).scalar_one()
        assert visible == 1
    finally:
        if recon_phase1f2_session.in_transaction():
            await recon_phase1f2_session.rollback()
        await recon_phase1f2_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_reconciliation_session(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(recon_phase1f2_session)
    await recon_phase1f2_session.execute(text("SET ROLE rls_recon_probe_user"))
    try:
        await ensure_tenant_context(recon_phase1f2_session, tenant_b)
        session_b = await seed_recon_session(
            recon_phase1f2_session,
            tenant_id=tenant_b,
            organisation_id=tenant_b,
            created_by=tenant_b,
            token_seed="rls_other",
        )
        await ensure_tenant_context(recon_phase1f2_session, tenant_a)
        visible = (
            await recon_phase1f2_session.execute(
                text("SELECT COUNT(*) FROM reconciliation_sessions WHERE id = :session_id"),
                {"session_id": str(session_b.id)},
            )
        ).scalar_one()
        assert visible == 0
    finally:
        if recon_phase1f2_session.in_transaction():
            await recon_phase1f2_session.rollback()
        await recon_phase1f2_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_reconciliation_session(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(recon_phase1f2_session)
    await recon_phase1f2_session.execute(text("SET ROLE rls_recon_probe_user"))
    try:
        await ensure_tenant_context(recon_phase1f2_session, tenant_a)
        with pytest.raises(DBAPIError):
            await AuditWriter.insert_financial_record(
                recon_phase1f2_session,
                model_class=ReconciliationSession,
                tenant_id=tenant_b,
                record_data={"session_token": hash64("forbidden")},
                values={
                    "organisation_id": tenant_b,
                    "reconciliation_type": "gl_vs_trial_balance",
                    "source_a_type": "gl_entries",
                    "source_a_ref": "a",
                    "source_b_type": "trial_balance_rows",
                    "source_b_ref": "b",
                    "period_start": text("'2026-01-01'::date"),
                    "period_end": text("'2026-01-31'::date"),
                    "matching_rule_version": "recon_match_v1",
                    "tolerance_rule_version": "recon_tolerance_v1",
                    "session_token": hash64("forbidden"),
                    "materiality_config_json": {},
                    "status": "created",
                    "created_by": tenant_b,
                },
            )
            await recon_phase1f2_session.flush()
        await recon_phase1f2_session.rollback()
    finally:
        await recon_phase1f2_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_reconciliation_bridge_tables(
    recon_phase1f2_session: AsyncSession,
) -> None:
    for table_name in RECON_TABLES:
        row = (
            await recon_phase1f2_session.execute(
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
