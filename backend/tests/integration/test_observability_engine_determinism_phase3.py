from __future__ import annotations

import uuid
from datetime import date

import pytest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.equity_engine import EquityRun
from financeops.db.models.lease import LeaseJournalEntry
from financeops.db.models.revenue import RevenueJournalEntry
from financeops.db.rls import set_tenant_context
from financeops.modules.equity_engine.domain.value_objects import EquityRunTokenInput
from financeops.modules.equity_engine.infrastructure.token_builder import build_equity_run_token
from financeops.modules.observability_engine.application.diff_service import DiffService
from financeops.modules.observability_engine.application.graph_service import GraphService
from financeops.modules.observability_engine.application.replay_service import ReplayService
from financeops.modules.observability_engine.application.run_service import RunService
from financeops.modules.observability_engine.application.validation_service import ValidationService
from financeops.modules.observability_engine.infrastructure.repository import (
    ObservabilityRepository,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _build_service(session: AsyncSession) -> RunService:
    repository = ObservabilityRepository(session)
    return RunService(
        repository=repository,
        validation_service=ValidationService(),
        diff_service=DiffService(),
        replay_service=ReplayService(),
        graph_service=GraphService(repository),
    )


async def _seed_equity_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> uuid.UUID:
    run_token = build_equity_run_token(
        EquityRunTokenInput(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            statement_definition_version_token="stmt_v1",
            line_definition_version_token="line_v1",
            rollforward_rule_version_token="rule_v1",
            source_mapping_version_token="map_v1",
            consolidation_run_ref_nullable=None,
            fx_translation_run_ref_nullable=None,
            ownership_consolidation_run_ref_nullable=None,
            run_status="completed",
        )
    )
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=EquityRun,
        tenant_id=tenant_id,
        record_data={"run_token": run_token},
        values={
            "organisation_id": organisation_id,
            "reporting_period": reporting_period,
            "statement_definition_version_token": "stmt_v1",
            "line_definition_version_token": "line_v1",
            "rollforward_rule_version_token": "rule_v1",
            "source_mapping_version_token": "map_v1",
            "consolidation_run_ref_nullable": None,
            "fx_translation_run_ref_nullable": None,
            "ownership_consolidation_run_ref_nullable": None,
            "run_token": run_token,
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="equity_run",
            resource_name=run_token,
        ),
    )
    return row.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_observability_diff_and_replay_are_deterministic_and_no_upstream_mutation(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)

    run_a_id = await _seed_equity_run(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
        reporting_period=date(2026, 1, 31),
    )
    run_b_id = await _seed_equity_run(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
        reporting_period=date(2026, 2, 28),
    )
    await async_session.flush()

    equity_count_before = await async_session.scalar(select(func.count()).select_from(EquityRun))
    revenue_journal_before = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_journal_before = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))

    service = _build_service(async_session)
    diff_a = await service.run_diff(
        tenant_id=tenant_id,
        base_run_id=run_a_id,
        compare_run_id=run_b_id,
        created_by=user_id,
    )
    diff_b = await service.run_diff(
        tenant_id=tenant_id,
        base_run_id=run_a_id,
        compare_run_id=run_b_id,
        created_by=user_id,
    )
    assert diff_a["summary"] == diff_b["summary"]
    assert diff_b["idempotent"] is True
    assert diff_a["drift_flag"] is True

    replay = await service.replay_validate(
        tenant_id=tenant_id,
        run_id=run_a_id,
        created_by=user_id,
    )
    assert replay["module_code"] == "equity_engine"
    assert replay["matches"] is True

    graph_a = await service.build_graph_snapshot(
        tenant_id=tenant_id,
        root_run_id=run_a_id,
        created_by=user_id,
    )
    graph_b = await service.latest_graph(tenant_id=tenant_id, root_run_id=run_a_id)
    assert graph_b is not None
    assert graph_a["deterministic_hash"] == graph_b["deterministic_hash"]

    equity_count_after = await async_session.scalar(select(func.count()).select_from(EquityRun))
    revenue_journal_after = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_journal_after = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    assert equity_count_before == equity_count_after
    assert revenue_journal_before == revenue_journal_after
    assert lease_journal_before == lease_journal_after

