from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.financial_risk_phase1f5_helpers import (
    build_financial_risk_service,
    ensure_tenant_context,
    seed_active_risk_configuration,
    seed_upstream_ratio_run,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_inputs_produce_identical_risk_run_token(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
    first = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    second = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_is_idempotent_and_no_duplicate_risk_results(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
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
        await financial_risk_phase1f5_session.execute(
            text("SELECT COUNT(*) FROM risk_results WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    assert result_count == first["result_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_source_set_changes_run_token(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["ratio_run_id"])],
        source_trend_run_ids=[],
        source_reconciliation_session_ids=[],
        created_by=tenant_id,
    )
    assert run_a["run_token"] != run_b["run_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_results_signals_rollforwards_ordering_is_stable(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
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
    first_results = await service.list_results(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    second_results = await service.list_results(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    first_signals = await service.list_signals(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    second_signals = await service.list_signals(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    first_roll = await service.list_rollforwards(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    second_roll = await service.list_rollforwards(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    assert first_results == second_results
    assert first_signals == second_signals
    assert first_roll == second_roll


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dependency_propagation_signal_is_persisted(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    upstream = await seed_upstream_ratio_run(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(financial_risk_phase1f5_session)
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
    signals = await service.list_signals(
        tenant_id=tenant_id,
        run_id=uuid.UUID(executed["run_id"]),
    )
    assert any(row["signal_type"] == "parent_risk_result" for row in signals)
