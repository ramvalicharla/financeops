from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.financial_risk_phase1f5_helpers import (
    FINANCIAL_RISK_TABLES,
    build_financial_risk_service,
    ensure_tenant_context,
    seed_active_risk_configuration,
    seed_upstream_ratio_run,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_risk_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_risk_probe_user"))
    for table_name in (
        "risk_definitions",
        "risk_runs",
        "risk_results",
    ):
        await session.execute(text(f"GRANT SELECT, INSERT ON {table_name} TO rls_risk_probe_user"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_risk_definition(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _configure_probe_role(financial_risk_phase1f5_session)
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    await financial_risk_phase1f5_session.execute(text("SET ROLE rls_risk_probe_user"))
    try:
        await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
        count = (
            await financial_risk_phase1f5_session.execute(text("SELECT COUNT(*) FROM risk_definitions"))
        ).scalar_one()
        assert count >= 1
    finally:
        if financial_risk_phase1f5_session.in_transaction():
            await financial_risk_phase1f5_session.rollback()
        await financial_risk_phase1f5_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_risk_definition(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(financial_risk_phase1f5_session)
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_b)
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=tenant_b,
        effective_from=date(2026, 1, 1),
    )
    await financial_risk_phase1f5_session.execute(text("SET ROLE rls_risk_probe_user"))
    try:
        await ensure_tenant_context(financial_risk_phase1f5_session, tenant_a)
        count = (
            await financial_risk_phase1f5_session.execute(text("SELECT COUNT(*) FROM risk_definitions"))
        ).scalar_one()
        assert count == 0
    finally:
        if financial_risk_phase1f5_session.in_transaction():
            await financial_risk_phase1f5_session.rollback()
        await financial_risk_phase1f5_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_risk_run(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(financial_risk_phase1f5_session)
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_a)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
    await service.create_run(
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=tenant_a,
    )

    await financial_risk_phase1f5_session.execute(text("SET ROLE rls_risk_probe_user"))
    try:
        await ensure_tenant_context(financial_risk_phase1f5_session, tenant_a)
        with pytest.raises(DBAPIError):
            await financial_risk_phase1f5_session.execute(
                text(
                    """
                    INSERT INTO risk_runs
                      (id, tenant_id, chain_hash, previous_hash, organisation_id,
                       reporting_period, risk_definition_version_token,
                       propagation_version_token, weight_version_token,
                       materiality_version_token, source_metric_run_ids_json,
                       source_variance_run_ids_json, source_trend_run_ids_json,
                       source_reconciliation_session_ids_json, run_token,
                       status, validation_summary_json, created_by)
                    VALUES
                      (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                       :reporting_period, :dtoken,
                       :ptoken, :wtoken,
                       :mtoken, :metric,
                       :variance, '[]'::jsonb,
                       '[]'::jsonb, :run_token,
                       'created', '{}'::jsonb, :created_by)
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
                    "ptoken": "b" * 64,
                    "wtoken": "c" * 64,
                    "mtoken": "d" * 64,
                    "metric": f'["{upstream["ratio_run_id"]}"]',
                    "variance": f'["{upstream["ratio_run_id"]}"]',
                    "run_token": uuid.uuid4().hex,
                    "created_by": str(tenant_b),
                },
            )
            await financial_risk_phase1f5_session.flush()
    finally:
        if financial_risk_phase1f5_session.in_transaction():
            await financial_risk_phase1f5_session.rollback()
        await financial_risk_phase1f5_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_financial_risk_tables(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    for table in FINANCIAL_RISK_TABLES:
        row = (
            await financial_risk_phase1f5_session.execute(
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
