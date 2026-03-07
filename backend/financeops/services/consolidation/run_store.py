from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.consolidation import ConsolidationRun


async def get_run_or_raise(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> ConsolidationRun:
    result = await session.execute(
        select(ConsolidationRun).where(
            ConsolidationRun.tenant_id == tenant_id,
            ConsolidationRun.id == run_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Consolidation run not found")
    return run
