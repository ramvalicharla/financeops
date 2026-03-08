from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    ensure_tenant_context,
    seed_active_anomaly_configuration,
    seed_upstream_for_anomaly,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_inputs_produce_identical_anomaly_run_token(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(anomaly_phase1f6_session)
    first = await service.create_run(
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
    second = await service.create_run(
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
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_is_idempotent_and_no_duplicate_anomaly_results(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(anomaly_phase1f6_session)
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
    first = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    second = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    assert second["idempotent"] is True
    result_count = (
        await anomaly_phase1f6_session.execute(
            text("SELECT COUNT(*) FROM anomaly_results WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    assert result_count == first["result_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_source_set_changes_run_token(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(anomaly_phase1f6_session)
    run_a = await service.create_run(
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
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    assert run_a["run_token"] != run_b["run_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_results_signals_rollforwards_and_evidence_ordering_are_stable(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(anomaly_phase1f6_session)
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
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    run_id = uuid.UUID(executed["run_id"])
    first_results = await service.list_results(tenant_id=tenant_id, run_id=run_id)
    second_results = await service.list_results(tenant_id=tenant_id, run_id=run_id)
    first_signals = await service.list_signals(tenant_id=tenant_id, run_id=run_id)
    second_signals = await service.list_signals(tenant_id=tenant_id, run_id=run_id)
    first_roll = await service.list_rollforwards(tenant_id=tenant_id, run_id=run_id)
    second_roll = await service.list_rollforwards(tenant_id=tenant_id, run_id=run_id)
    first_evidence = await service.list_evidence(tenant_id=tenant_id, run_id=run_id)
    second_evidence = await service.list_evidence(tenant_id=tenant_id, run_id=run_id)
    assert first_results == second_results
    assert first_signals == second_signals
    assert first_roll == second_roll
    assert first_evidence == second_evidence
    assert all("z_score" in row for row in first_results)
