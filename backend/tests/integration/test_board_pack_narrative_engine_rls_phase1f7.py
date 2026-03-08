from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.board_pack_phase1f7_helpers import (
    BOARD_PACK_TABLES,
    ensure_tenant_context,
    seed_active_board_pack_configuration,
    seed_upstream_for_board_pack,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_board_pack_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_board_pack_probe_user"))
    for table_name in ("board_pack_definitions", "board_pack_runs", "board_pack_section_results"):
        await session.execute(
            text(f"GRANT SELECT, INSERT ON {table_name} TO rls_board_pack_probe_user")
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_board_pack_definition(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _configure_probe_role(board_pack_phase1f7_session)
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_id)
    await seed_active_board_pack_configuration(
        board_pack_phase1f7_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    await board_pack_phase1f7_session.execute(text("SET ROLE rls_board_pack_probe_user"))
    try:
        await ensure_tenant_context(board_pack_phase1f7_session, tenant_id)
        count = (
            await board_pack_phase1f7_session.execute(
                text("SELECT COUNT(*) FROM board_pack_definitions")
            )
        ).scalar_one()
        assert count >= 1
    finally:
        if board_pack_phase1f7_session.in_transaction():
            await board_pack_phase1f7_session.rollback()
        await board_pack_phase1f7_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_board_pack_definition(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(board_pack_phase1f7_session)
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_b)
    await seed_active_board_pack_configuration(
        board_pack_phase1f7_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=tenant_b,
        effective_from=date(2026, 1, 1),
    )
    await board_pack_phase1f7_session.execute(text("SET ROLE rls_board_pack_probe_user"))
    try:
        await ensure_tenant_context(board_pack_phase1f7_session, tenant_a)
        count = (
            await board_pack_phase1f7_session.execute(
                text("SELECT COUNT(*) FROM board_pack_definitions")
            )
        ).scalar_one()
        assert count == 0
    finally:
        if board_pack_phase1f7_session.in_transaction():
            await board_pack_phase1f7_session.rollback()
        await board_pack_phase1f7_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_board_pack_run(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(board_pack_phase1f7_session)
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_a)
    upstream = await seed_upstream_for_board_pack(
        board_pack_phase1f7_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        board_pack_phase1f7_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        effective_from=date(2026, 1, 1),
    )
    await board_pack_phase1f7_session.execute(text("SET ROLE rls_board_pack_probe_user"))
    try:
        await ensure_tenant_context(board_pack_phase1f7_session, tenant_a)
        with pytest.raises(DBAPIError):
            await board_pack_phase1f7_session.execute(
                text(
                    """
                    INSERT INTO board_pack_runs
                      (id, tenant_id, chain_hash, previous_hash, organisation_id,
                       reporting_period, board_pack_definition_version_token,
                       section_definition_version_token, narrative_template_version_token,
                       inclusion_rule_version_token, source_metric_run_ids_json,
                       source_risk_run_ids_json, source_anomaly_run_ids_json,
                       run_token, status, validation_summary_json, created_by)
                    VALUES
                      (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                       :reporting_period, :dtoken,
                       :stoken, :ttoken,
                       :itoken, :metric,
                       :risk, :anomaly,
                       :run_token, 'created', '{}'::jsonb, :created_by)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(tenant_b),
                    "chain_hash": "1" * 64,
                    "previous_hash": "0" * 64,
                    "organisation_id": str(tenant_b),
                    "reporting_period": date(2026, 1, 31),
                    "dtoken": "a" * 64,
                    "stoken": "b" * 64,
                    "ttoken": "c" * 64,
                    "itoken": "d" * 64,
                    "metric": f'["{upstream["metric_run_id"]}"]',
                    "risk": f'["{upstream["risk_run_id"]}"]',
                    "anomaly": f'["{upstream["anomaly_run_id"]}"]',
                    "run_token": uuid.uuid4().hex,
                    "created_by": str(tenant_b),
                },
            )
            await board_pack_phase1f7_session.flush()
    finally:
        if board_pack_phase1f7_session.in_transaction():
            await board_pack_phase1f7_session.rollback()
        await board_pack_phase1f7_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_board_pack_tables(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    for table in BOARD_PACK_TABLES:
        row = (
            await board_pack_phase1f7_session.execute(
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
