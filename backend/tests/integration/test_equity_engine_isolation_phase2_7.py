from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import LeaseJournalEntry
from financeops.db.models.prepaid import PrepaidJournalEntry
from financeops.db.models.revenue import RevenueJournalEntry
from financeops.db.rls import set_tenant_context
from financeops.modules.equity_engine.application.mapping_service import MappingService
from financeops.modules.equity_engine.application.rollforward_service import RollforwardService
from financeops.modules.equity_engine.application.run_service import RunService
from financeops.modules.equity_engine.application.validation_service import ValidationService
from financeops.modules.equity_engine.infrastructure.repository import EquityRepository
from tests.integration.test_equity_engine_determinism_phase2_7 import (
    _seed_active_equity_definitions,
    _seed_source_runs,
)


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=EquityRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        rollforward_service=RollforwardService(),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_execution_has_no_accounting_engine_side_effects(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)

    await _seed_active_equity_definitions(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    consolidation_run_id, fx_run_id, ownership_run_id = await _seed_source_runs(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    await async_session.flush()

    revenue_before = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_before = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    prepaid_before = await async_session.scalar(select(func.count()).select_from(PrepaidJournalEntry))

    service = _build_service(async_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        consolidation_run_ref_nullable=consolidation_run_id,
        fx_translation_run_ref_nullable=fx_run_id,
        ownership_consolidation_run_ref_nullable=ownership_run_id,
        created_by=user_id,
    )
    await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        created_by=user_id,
    )

    revenue_after = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_after = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    prepaid_after = await async_session.scalar(select(func.count()).select_from(PrepaidJournalEntry))

    assert revenue_before == revenue_after
    assert lease_before == lease_after
    assert prepaid_before == prepaid_after
