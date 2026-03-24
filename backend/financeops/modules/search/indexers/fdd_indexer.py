from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.fdd.models import FDDEngagement
from financeops.modules.search.service import upsert_index_entry


async def index_fdd_engagement(session: AsyncSession, engagement: FDDEngagement) -> None:
    await upsert_index_entry(
        session,
        tenant_id=engagement.tenant_id,
        entity_type="fdd_engagement",
        entity_id=engagement.id,
        title=engagement.engagement_name,
        subtitle=engagement.target_company_name,
        body=None,
        url=f"/advisory/fdd/{engagement.id}",
        metadata={"status": engagement.status},
    )


async def reindex_all_fdd(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(FDDEngagement).where(FDDEngagement.tenant_id == tenant_id)
        )
    ).scalars().all()
    for row in rows:
        await index_fdd_engagement(session, row)
    return len(rows)


__all__ = ["index_fdd_engagement", "reindex_all_fdd"]

