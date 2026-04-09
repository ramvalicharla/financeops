from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.users import IamUser, UserRole
from tests.integration.board_pack_phase1f7_helpers import (
    build_board_pack_service,
    ensure_tenant_context,
    seed_active_board_pack_configuration,
    seed_identity_user,
    seed_upstream_for_board_pack,
)
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    _create_test_mutation_context,
)

ENGINE_TABLES = (
    "revenue_schedules",
    "lease_liability_schedule",
    "prepaid_amortization_schedule",
    "asset_depreciation_schedule",
)

JOURNAL_TABLES = (
    "revenue_journal_entries",
    "lease_journal_entries",
    "prepaid_journal_entries",
    "asset_journal_entries",
)

UPSTREAM_TABLES = (
    "metric_runs",
    "metric_results",
    "variance_results",
    "trend_results",
    "risk_runs",
    "risk_results",
    "anomaly_runs",
    "anomaly_results",
    "anomaly_contributing_signals",
    "anomaly_rollforward_events",
    "anomaly_evidence_links",
    "reconciliation_sessions",
    "reconciliation_lines",
    "reconciliation_exceptions",
    "normalization_runs",
    "payroll_normalized_lines",
    "gl_normalized_lines",
)

FX_TABLES = (
    "fx_rate_fetch_runs",
    "fx_rate_quotes",
    "fx_manual_monthly_rates",
    "fx_variance_results",
)


async def _board_pack_mutation_context(session: AsyncSession, tenant_id: uuid.UUID):
    user = (
        await session.execute(select(IamUser).where(IamUser.id == tenant_id))
    ).scalar_one_or_none()
    if user is None:
        user = await seed_identity_user(
            session,
            tenant_id=tenant_id,
            user_id=tenant_id,
            email=f"{tenant_id.hex[:12]}@example.com",
            role=UserRole.finance_leader,
        )
    mutation_context = await _create_test_mutation_context(
        session,
        tenant_id=tenant_id,
        actor_user_id=user.id,
        actor_role=user.role.value,
        module_key="board_pack_narrative_engine",
        intent_type="TEST_BOARD_PACK_RUN",
    )
    return governed_mutation_context(mutation_context)


async def _counts(session: AsyncSession, tables: tuple[str, ...]) -> dict[str, int]:
    data: dict[str, int] = {}
    for table in tables:
        count = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
        data[table] = int(count)
    return data


async def _run_board_pack_flow(session: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    await ensure_tenant_context(session, tenant_id)
    upstream = await seed_upstream_for_board_pack(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_board_pack_service(session)
    with await _board_pack_mutation_context(session, tenant_id):
        created = await service.create_run(
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            reporting_period=date(2026, 1, 31),
            source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
            source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
            source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
            created_by=tenant_id,
        )
    with await _board_pack_mutation_context(session, tenant_id):
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_run_does_not_modify_engine_or_journal_tables(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_id)
    before_engine = await _counts(board_pack_phase1f7_session, ENGINE_TABLES)
    before_journal = await _counts(board_pack_phase1f7_session, JOURNAL_TABLES)
    await _run_board_pack_flow(board_pack_phase1f7_session, tenant_id=tenant_id)
    after_engine = await _counts(board_pack_phase1f7_session, ENGINE_TABLES)
    after_journal = await _counts(board_pack_phase1f7_session, JOURNAL_TABLES)
    assert before_engine == after_engine
    assert before_journal == after_journal


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_run_does_not_mutate_upstream_layers(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_id)
    upstream = await seed_upstream_for_board_pack(
        board_pack_phase1f7_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        board_pack_phase1f7_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    before_upstream = await _counts(board_pack_phase1f7_session, UPSTREAM_TABLES)
    service = build_board_pack_service(board_pack_phase1f7_session)
    with await _board_pack_mutation_context(board_pack_phase1f7_session, tenant_id):
        created = await service.create_run(
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            reporting_period=date(2026, 1, 31),
            source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
            source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
            source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
            created_by=tenant_id,
        )
    with await _board_pack_mutation_context(board_pack_phase1f7_session, tenant_id):
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )
    after_upstream = await _counts(board_pack_phase1f7_session, UPSTREAM_TABLES)
    assert before_upstream == after_upstream


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_run_does_not_invoke_fx_tables(
    board_pack_phase1f7_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(board_pack_phase1f7_session, tenant_id)
    before_fx = await _counts(board_pack_phase1f7_session, FX_TABLES)
    await _run_board_pack_flow(board_pack_phase1f7_session, tenant_id=tenant_id)
    after_fx = await _counts(board_pack_phase1f7_session, FX_TABLES)
    assert before_fx == after_fx
