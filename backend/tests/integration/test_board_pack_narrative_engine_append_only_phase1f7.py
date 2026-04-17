from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.users import IamUser, UserRole
from financeops.db.append_only import APPEND_ONLY_TABLES
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


async def _seed_executed_run(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, str]:
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
        return await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(created["run_id"]),
            actor_user_id=tenant_id,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_definitions_allow_update_for_definition_lifecycle(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            await ensure_tenant_context(session, tenant_id)
            seeded = await seed_active_board_pack_configuration(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                created_by=tenant_id,
                effective_from=date(2026, 1, 1),
            )
            await session.execute(
                text("UPDATE board_pack_definitions SET board_pack_name='changed' WHERE id=:id"),
                {"id": seeded["board_pack_definition_id"]},
            )
            await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_runs_results_and_sections(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            executed = await _seed_executed_run(session, tenant_id=tenant_id)
            run_id = executed["run_id"]
            section_id = (
                await session.execute(
                    text("SELECT id FROM board_pack_section_results WHERE run_id=:run_id LIMIT 1"),
                    {"run_id": run_id},
                )
            ).scalar_one()

            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE board_pack_runs SET status='failed' WHERE id=:id"),
                    {"id": run_id},
                )
                await session.flush()
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE board_pack_results SET status='failed' WHERE run_id=:run_id"),
                    {"run_id": run_id},
                )
                await session.flush()
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE board_pack_section_results SET section_title='x' WHERE id=:id"),
                    {"id": str(section_id)},
                )
                await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_narrative_blocks_and_evidence(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            executed = await _seed_executed_run(session, tenant_id=tenant_id)
            run_id = executed["run_id"]
            narrative_id = (
                await session.execute(
                    text("SELECT id FROM board_pack_narrative_blocks WHERE run_id=:run_id LIMIT 1"),
                    {"run_id": run_id},
                )
            ).scalar_one()
            evidence_id = (
                await session.execute(
                    text("SELECT id FROM board_pack_evidence_links WHERE run_id=:run_id LIMIT 1"),
                    {"run_id": run_id},
                )
            ).scalar_one()

            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE board_pack_narrative_blocks SET narrative_text='x' WHERE id=:id"),
                    {"id": str(narrative_id)},
                )
                await session.flush()
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE board_pack_evidence_links SET evidence_label='x' WHERE id=:id"),
                    {"id": str(evidence_id)},
                )
                await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_all_board_pack_tables() -> None:
    required = {
        "board_pack_section_definitions",
        "narrative_templates",
        "board_pack_inclusion_rules",
        "board_pack_runs",
        "board_pack_results",
        "board_pack_section_results",
        "board_pack_narrative_blocks",
        "board_pack_evidence_links",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))
