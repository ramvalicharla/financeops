from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.ratio_variance_phase1f4_helpers import (
    build_ratio_variance_service,
    ensure_tenant_context,
    seed_active_definition_set,
    seed_finalized_normalization_pair,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_inputs_produce_identical_run_token(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_definition_set(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_ratio_variance_service(ratio_phase1f4_session)
    first = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=tenant_id,
    )
    second = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=tenant_id,
    )
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_is_idempotent_and_no_duplicate_results(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_definition_set(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_ratio_variance_service(ratio_phase1f4_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
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
    metric_count = (
        await ratio_phase1f4_session.execute(
            text("SELECT COUNT(*) FROM metric_results WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    assert metric_count == first["metric_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_scope_changes_run_token(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_definition_set(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_ratio_variance_service(ratio_phase1f4_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=tenant_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE2"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=tenant_id,
    )
    assert run_a["run_token"] != run_b["run_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_metrics_variances_trends_ordering_stable(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_definition_set(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_ratio_variance_service(ratio_phase1f4_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=tenant_id,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    first_metrics = await service.list_metrics(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    second_metrics = await service.list_metrics(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    first_variances = await service.list_variances(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    second_variances = await service.list_variances(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    first_trends = await service.list_trends(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    second_trends = await service.list_trends(tenant_id=tenant_id, run_id=uuid.UUID(executed["run_id"]))
    assert first_metrics == second_metrics
    assert first_variances == second_variances
    assert first_trends == second_trends
