from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.anomaly_pattern_phase1f6_helpers import (
    ANOMALY_TABLES,
    ensure_tenant_context,
    seed_active_anomaly_configuration,
    seed_upstream_for_anomaly,
)


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_anomaly_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_anomaly_probe_user"))
    for table_name in ("anomaly_definitions", "anomaly_runs", "anomaly_results"):
        await session.execute(
            text(f"GRANT SELECT, INSERT ON {table_name} TO rls_anomaly_probe_user")
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_anomaly_definition(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _configure_probe_role(anomaly_phase1f6_session)
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    await anomaly_phase1f6_session.execute(text("SET ROLE rls_anomaly_probe_user"))
    try:
        await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
        count = (
            await anomaly_phase1f6_session.execute(
                text("SELECT COUNT(*) FROM anomaly_definitions")
            )
        ).scalar_one()
        assert count >= 1
    finally:
        if anomaly_phase1f6_session.in_transaction():
            await anomaly_phase1f6_session.rollback()
        await anomaly_phase1f6_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_anomaly_definition(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(anomaly_phase1f6_session)
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_b)
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=tenant_b,
        effective_from=date(2026, 1, 1),
    )
    await anomaly_phase1f6_session.execute(text("SET ROLE rls_anomaly_probe_user"))
    try:
        await ensure_tenant_context(anomaly_phase1f6_session, tenant_a)
        count = (
            await anomaly_phase1f6_session.execute(
                text("SELECT COUNT(*) FROM anomaly_definitions")
            )
        ).scalar_one()
        assert count == 0
    finally:
        if anomaly_phase1f6_session.in_transaction():
            await anomaly_phase1f6_session.rollback()
        await anomaly_phase1f6_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_anomaly_run(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _configure_probe_role(anomaly_phase1f6_session)
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_a)
    upstream = await seed_upstream_for_anomaly(
        anomaly_phase1f6_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_a,
        organisation_id=tenant_a,
        created_by=tenant_a,
        effective_from=date(2026, 1, 1),
    )
    await anomaly_phase1f6_session.execute(text("SET ROLE rls_anomaly_probe_user"))
    try:
        await ensure_tenant_context(anomaly_phase1f6_session, tenant_a)
        with pytest.raises(DBAPIError):
            await anomaly_phase1f6_session.execute(
                text(
                    """
                    INSERT INTO anomaly_runs
                      (id, tenant_id, chain_hash, previous_hash, organisation_id,
                       reporting_period, anomaly_definition_version_token,
                       pattern_rule_version_token, persistence_rule_version_token,
                       correlation_rule_version_token, statistical_rule_version_token,
                       source_metric_run_ids_json, source_variance_run_ids_json,
                       source_trend_run_ids_json, source_risk_run_ids_json,
                       source_reconciliation_session_ids_json, run_token,
                       status, validation_summary_json, created_by)
                    VALUES
                      (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                       :reporting_period, :dtoken,
                       :ptoken, :pstoken,
                       :ctoken, :stoken,
                       :metric, :variance,
                       :trend, :risk,
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
                    "pstoken": "c" * 64,
                    "ctoken": "d" * 64,
                    "stoken": "e" * 64,
                    "metric": f'["{upstream["metric_run_id"]}"]',
                    "variance": f'["{upstream["metric_run_id"]}"]',
                    "trend": f'["{upstream["metric_run_id"]}"]',
                    "risk": f'["{upstream["risk_run_id"]}"]',
                    "run_token": uuid.uuid4().hex,
                    "created_by": str(tenant_b),
                },
            )
            await anomaly_phase1f6_session.flush()
    finally:
        if anomaly_phase1f6_session.in_transaction():
            await anomaly_phase1f6_session.rollback()
        await anomaly_phase1f6_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_anomaly_tables(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    for table in ANOMALY_TABLES:
        row = (
            await anomaly_phase1f6_session.execute(
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
