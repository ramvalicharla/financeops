from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.board_pack_phase1f7_helpers import (
    build_board_pack_service,
    ensure_tenant_context,
    seed_active_board_pack_configuration,
    seed_upstream_for_board_pack,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_inputs_produce_identical_board_pack_run_token(
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
    service = build_board_pack_service(board_pack_phase1f7_session)
    first = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=tenant_id,
    )
    second = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=tenant_id,
    )
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_is_idempotent_and_no_duplicate_board_pack_outputs(
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
    service = build_board_pack_service(board_pack_phase1f7_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
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
    section_count = (
        await board_pack_phase1f7_session.execute(
            text("SELECT COUNT(*) FROM board_pack_section_results WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    narrative_count = (
        await board_pack_phase1f7_session.execute(
            text("SELECT COUNT(*) FROM board_pack_narrative_blocks WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    evidence_count = (
        await board_pack_phase1f7_session.execute(
            text("SELECT COUNT(*) FROM board_pack_evidence_links WHERE run_id=:run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    assert section_count == first["section_count"]
    assert narrative_count == first["narrative_count"]
    assert evidence_count == first["evidence_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_reporting_period_changes_run_token(
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
    service = build_board_pack_service(board_pack_phase1f7_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=tenant_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 2, 28),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=tenant_id,
    )
    assert run_a["run_token"] != run_b["run_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sections_narratives_and_evidence_ordering_are_stable(
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
    service = build_board_pack_service(board_pack_phase1f7_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=tenant_id,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    run_id = uuid.UUID(executed["run_id"])
    first_sections = await service.list_sections(tenant_id=tenant_id, run_id=run_id)
    second_sections = await service.list_sections(tenant_id=tenant_id, run_id=run_id)
    first_narratives = await service.list_narratives(tenant_id=tenant_id, run_id=run_id)
    second_narratives = await service.list_narratives(tenant_id=tenant_id, run_id=run_id)
    first_evidence = await service.list_evidence(tenant_id=tenant_id, run_id=run_id)
    second_evidence = await service.list_evidence(tenant_id=tenant_id, run_id=run_id)
    assert first_sections == second_sections
    assert first_narratives == second_narratives
    assert first_evidence == second_evidence
    assert all("section_order" in row for row in first_sections)
