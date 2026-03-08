from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    ensure_tenant_context,
    seed_active_anomaly_configuration,
    seed_upstream_for_anomaly,
)


async def _seed_executed_run(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, str]:
    await ensure_tenant_context(session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    return await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_anomaly_definitions(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    seeded = await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_definitions SET anomaly_name='changed' WHERE id=:id"),
            {"id": seeded["anomaly_definition_id"]},
        )
        await anomaly_phase1f6_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_runs_results_and_signals(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    executed = await _seed_executed_run(anomaly_phase1f6_session, tenant_id=tenant_id)
    run_id = executed["run_id"]
    result_id = (
        await anomaly_phase1f6_session.execute(
            text("SELECT id FROM anomaly_results WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    signal_id = (
        await anomaly_phase1f6_session.execute(
            text("SELECT id FROM anomaly_contributing_signals WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_runs SET status='failed' WHERE id=:id"),
            {"id": run_id},
        )
        await anomaly_phase1f6_session.flush()
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_results SET anomaly_score=0 WHERE id=:id"),
            {"id": str(result_id)},
        )
        await anomaly_phase1f6_session.flush()
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_contributing_signals SET signal_ref='x' WHERE id=:id"),
            {"id": str(signal_id)},
        )
        await anomaly_phase1f6_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_rollforwards_and_evidence(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    executed = await _seed_executed_run(anomaly_phase1f6_session, tenant_id=tenant_id)
    run_id = executed["run_id"]
    rollforward_id = (
        await anomaly_phase1f6_session.execute(
            text("SELECT id FROM anomaly_rollforward_events WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    evidence_id = (
        await anomaly_phase1f6_session.execute(
            text("SELECT id FROM anomaly_evidence_links WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_rollforward_events SET event_type='resolved' WHERE id=:id"),
            {"id": str(rollforward_id)},
        )
        await anomaly_phase1f6_session.flush()
    with pytest.raises(DBAPIError):
        await anomaly_phase1f6_session.execute(
            text("UPDATE anomaly_evidence_links SET evidence_label='x' WHERE id=:id"),
            {"id": str(evidence_id)},
        )
        await anomaly_phase1f6_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_all_anomaly_tables() -> None:
    required = {
        "anomaly_definitions",
        "anomaly_pattern_rules",
        "anomaly_persistence_rules",
        "anomaly_correlation_rules",
        "anomaly_statistical_rules",
        "anomaly_runs",
        "anomaly_results",
        "anomaly_contributing_signals",
        "anomaly_rollforward_events",
        "anomaly_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
