from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from unittest.mock import AsyncMock, patch

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationEntity,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditWriter
from financeops.services.consolidation import (
    EntitySnapshotMapping,
    create_or_get_run,
    finalize_run,
    get_run_status,
    mark_run_running,
    prepare_entities_for_run,
)


def _uuid(value: str) -> UUID:
    return UUID(value)


async def _seed_snapshot(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    entity_id: UUID,
) -> NormalizedFinancialSnapshot:
    snapshot = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "svc-src",
        },
        values={
            "entity_id": entity_id,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "svc-src",
            "supersedes_snapshot_id": None,
            "correlation_id": "corr-svc-snap",
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot.id),
            "account_code": "4000",
            "local_amount": "100.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot.id,
            "account_code": "4000",
            "local_amount": Decimal("100.000000"),
            "currency": "USD",
            "ic_reference": None,
            "counterparty_entity": None,
            "transaction_date": None,
            "ic_account_class": None,
            "correlation_id": "corr-svc-line",
        },
    )
    return snapshot


@pytest.mark.asyncio
async def test_create_or_get_run_is_idempotent(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000411")
    snapshot = await _seed_snapshot(async_session, tenant_id=test_tenant.id, entity_id=entity_id)

    first = await create_or_get_run(
        async_session,
        tenant_id=test_tenant.id,
        initiated_by=test_tenant.id,
        period_year=2026,
        period_month=3,
        parent_currency="USD",
        rate_mode="daily",
        mappings=[EntitySnapshotMapping(entity_id=entity_id, snapshot_id=snapshot.id)],
        amount_tolerance_parent=None,
        fx_explained_tolerance_parent=None,
        timing_tolerance_days=None,
        correlation_id="corr-run-1",
    )
    second = await create_or_get_run(
        async_session,
        tenant_id=test_tenant.id,
        initiated_by=test_tenant.id,
        period_year=2026,
        period_month=3,
        parent_currency="USD",
        rate_mode="daily",
        mappings=[EntitySnapshotMapping(entity_id=entity_id, snapshot_id=snapshot.id)],
        amount_tolerance_parent=None,
        fx_explained_tolerance_parent=None,
        timing_tolerance_days=None,
        correlation_id="corr-run-1",
    )

    assert first.created_new is True
    assert second.created_new is False
    assert first.run_id == second.run_id


@pytest.mark.asyncio
async def test_prepare_entities_and_run_status_lifecycle(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    entity_id = _uuid("00000000-0000-0000-0000-000000000422")
    snapshot = await _seed_snapshot(async_session, tenant_id=test_tenant.id, entity_id=entity_id)
    run = await create_or_get_run(
        async_session,
        tenant_id=test_tenant.id,
        initiated_by=test_tenant.id,
        period_year=2026,
        period_month=3,
        parent_currency="USD",
        rate_mode="daily",
        mappings=[EntitySnapshotMapping(entity_id=entity_id, snapshot_id=snapshot.id)],
        amount_tolerance_parent=None,
        fx_explained_tolerance_parent=None,
        timing_tolerance_days=None,
        correlation_id="corr-run-2",
    )

    await mark_run_running(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.run_id,
        user_id=test_tenant.id,
        correlation_id="corr-run-2",
    )
    with patch(
        "financeops.services.consolidation.consolidation_service.resolve_expected_rate_for_entity",
        new=AsyncMock(return_value=Decimal("1.000000")),
    ), patch(
        "financeops.services.consolidation.consolidation_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        count = await prepare_entities_for_run(
            async_session,
            tenant_id=test_tenant.id,
            run_id=run.run_id,
            user_id=test_tenant.id,
            correlation_id="corr-run-2",
        )
    assert count == 1
    assert spy.await_count >= 1

    status_running = await get_run_status(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.run_id,
    )
    assert status_running["status"] == "running"

    terminal = await finalize_run(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.run_id,
        user_id=test_tenant.id,
        correlation_id="corr-run-2",
        event_type="completed",
        metadata_json={"result_count": 0},
    )
    assert terminal.event_type == "completed"

    # Terminal event is immutable/idempotent: subsequent finalize returns existing terminal.
    same_terminal = await finalize_run(
        async_session,
        tenant_id=test_tenant.id,
        run_id=run.run_id,
        user_id=test_tenant.id,
        correlation_id="corr-run-2",
        event_type="failed",
        metadata_json={"error": "ignored"},
    )
    assert same_terminal.event_type == "completed"

    entities = (
        await async_session.execute(
            ConsolidationEntity.__table__.select().where(
                ConsolidationEntity.tenant_id == test_tenant.id,
                ConsolidationEntity.run_id == run.run_id,
            )
        )
    ).all()
    assert len(entities) == 1
