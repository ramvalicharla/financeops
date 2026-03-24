from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisNormalizedLine
from financeops.modules.search.service import upsert_index_entry


async def index_mis_line(session: AsyncSession, mis_line: MisNormalizedLine) -> None:
    await upsert_index_entry(
        session,
        tenant_id=mis_line.tenant_id,
        entity_type="mis_line",
        entity_id=mis_line.id,
        title=mis_line.canonical_metric_code,
        subtitle=mis_line.source_row_ref,
        body=mis_line.source_column_ref,
        url="/mis",
        metadata={
            "currency_code": mis_line.currency_code,
            "period_value": str(mis_line.period_value),
            "validation_status": mis_line.validation_status,
        },
    )


async def reindex_all_mis_lines(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(MisNormalizedLine).where(MisNormalizedLine.tenant_id == tenant_id)
        )
    ).scalars().all()
    for row in rows:
        await index_mis_line(session, row)
    return len(rows)


__all__ = ["index_mis_line", "reindex_all_mis_lines"]

