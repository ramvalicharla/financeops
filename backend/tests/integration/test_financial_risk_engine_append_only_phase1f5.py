from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from tests.integration.financial_risk_phase1f5_helpers import (
    build_financial_risk_service,
    ensure_tenant_context,
    seed_active_risk_configuration,
    seed_upstream_ratio_run,
)


async def _seed_executed_run(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, str]:
    await ensure_tenant_context(session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
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
async def test_append_only_rejects_update_on_risk_definitions(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    seeded = await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_definitions SET risk_name='changed' WHERE id=:id"),
            {"id": seeded["risk_definition_id"]},
        )
        await financial_risk_phase1f5_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_runs_results_and_signals(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    executed = await _seed_executed_run(financial_risk_phase1f5_session, tenant_id=tenant_id)
    run_id = executed["run_id"]
    result_id = (
        await financial_risk_phase1f5_session.execute(
            text("SELECT id FROM risk_results WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    signal_id = (
        await financial_risk_phase1f5_session.execute(
            text("SELECT id FROM risk_contributing_signals WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()

    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_runs SET status='failed' WHERE id=:id"),
            {"id": run_id},
        )
        await financial_risk_phase1f5_session.flush()
    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_results SET risk_score=0 WHERE id=:id"),
            {"id": str(result_id)},
        )
        await financial_risk_phase1f5_session.flush()
    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_contributing_signals SET signal_ref='x' WHERE id=:id"),
            {"id": str(signal_id)},
        )
        await financial_risk_phase1f5_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_rollforwards_and_evidence(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    executed = await _seed_executed_run(financial_risk_phase1f5_session, tenant_id=tenant_id)
    run_id = executed["run_id"]
    rollforward_id = (
        await financial_risk_phase1f5_session.execute(
            text("SELECT id FROM risk_rollforward_events WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    evidence_id = (
        await financial_risk_phase1f5_session.execute(
            text("SELECT id FROM risk_evidence_links WHERE run_id=:run_id LIMIT 1"),
            {"run_id": run_id},
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_rollforward_events SET event_type='resolved' WHERE id=:id"),
            {"id": str(rollforward_id)},
        )
        await financial_risk_phase1f5_session.flush()
    with pytest.raises(DBAPIError):
        await financial_risk_phase1f5_session.execute(
            text("UPDATE risk_evidence_links SET evidence_label='x' WHERE id=:id"),
            {"id": str(evidence_id)},
        )
        await financial_risk_phase1f5_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_financial_risk_tables() -> None:
    required = {
        "risk_definitions",
        "risk_definition_dependencies",
        "risk_weight_configurations",
        "risk_materiality_rules",
        "risk_runs",
        "risk_results",
        "risk_contributing_signals",
        "risk_rollforward_events",
        "risk_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
