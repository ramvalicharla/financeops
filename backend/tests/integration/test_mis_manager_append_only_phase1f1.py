from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from financeops.modules.mis_manager.infrastructure.repository import MisManagerRepository
from tests.integration.mis_phase1f1_helpers import (
    ensure_tenant_context,
    seed_mis_drift_event,
    seed_mis_exception,
    seed_mis_normalized_line,
    seed_mis_snapshot,
    seed_mis_template,
    seed_mis_template_version,
)


async def _seed_graph(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    await ensure_tenant_context(session, tenant_id)
    template = await seed_mis_template(
        session,
        tenant_id=tenant_id,
        template_code=f"append_only_{uuid.uuid4().hex[:8]}",
    )
    v1 = await seed_mis_template_version(
        session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="append_v1",
        structure_seed="append_v1",
        status="active",
    )
    v2 = await seed_mis_template_version(
        session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=2,
        version_token_seed="append_v2",
        structure_seed="append_v2",
        status="candidate",
        supersedes_id=v1.id,
        based_on_version_id=v1.id,
    )
    snapshot = await seed_mis_snapshot(
        session,
        tenant_id=tenant_id,
        template_id=template.id,
        template_version_id=v1.id,
        reporting_period=date(2026, 1, 31),
        snapshot_token_seed="append_snapshot",
    )
    line = await seed_mis_normalized_line(
        session,
        tenant_id=tenant_id,
        snapshot_id=snapshot.id,
        line_no=1,
    )
    exc = await seed_mis_exception(
        session,
        tenant_id=tenant_id,
        snapshot_id=snapshot.id,
    )
    drift = await seed_mis_drift_event(
        session,
        tenant_id=tenant_id,
        template_id=template.id,
        prior_template_version_id=v1.id,
        candidate_template_version_id=v2.id,
    )
    await session.flush()
    return {
        "template": template,
        "version": v1,
        "snapshot": snapshot,
        "line": line,
        "exception": exc,
        "drift": drift,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_mis_template_versions(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text("UPDATE mis_template_versions SET status = 'rejected' WHERE id = :id"),
            {"id": str(graph["version"].id)},
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_mis_data_snapshots(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text(
                "UPDATE mis_data_snapshots SET snapshot_status = 'validated' WHERE id = :id"
            ),
            {"id": str(graph["snapshot"].id)},
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_mis_normalized_lines(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text("UPDATE mis_normalized_lines SET currency_code = 'EUR' WHERE id = :id"),
            {"id": str(graph["line"].id)},
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_mis_ingestion_exceptions_if_append_only(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text(
                "UPDATE mis_ingestion_exceptions SET resolution_status = 'resolved' WHERE id = :id"
            ),
            {"id": str(graph["exception"].id)},
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_mis_drift_events_if_append_only(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text("UPDATE mis_drift_events SET decision_status = 'accepted' WHERE id = :id"),
            {"id": str(graph["drift"].id)},
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_all_mis_tables() -> None:
    required = {
        "mis_templates",
        "mis_uploads",
        "mis_template_versions",
        "mis_template_sections",
        "mis_template_columns",
        "mis_template_row_mappings",
        "mis_data_snapshots",
        "mis_normalized_lines",
        "mis_ingestion_exceptions",
        "mis_drift_events",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_repository_does_not_bypass_append_only_protections(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    graph = await _seed_graph(mis_phase1f1_session, tenant_id)
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    repository = MisManagerRepository(mis_phase1f1_session)
    snapshot = await repository.get_snapshot(
        tenant_id=tenant_id,
        snapshot_id=graph["snapshot"].id,
    )
    assert snapshot is not None
    with pytest.raises(DBAPIError):
        await mis_phase1f1_session.execute(
            text(
                "DELETE FROM mis_data_snapshots WHERE id = :id"
            ),
            {"id": str(graph["snapshot"].id)},
        )
