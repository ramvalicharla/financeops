from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.marketplace.models import MarketplaceTemplate
from financeops.modules.search.service import upsert_index_entry


async def index_template(session: AsyncSession, template: MarketplaceTemplate) -> None:
    if template.status != "published":
        return
    await upsert_index_entry(
        session,
        tenant_id=template.tenant_id,
        entity_type="marketplace_template",
        entity_id=template.id,
        title=template.title,
        subtitle=template.description,
        body=None,
        url=f"/marketplace/{template.id}",
        metadata={
            "template_type": template.template_type,
            "industry": template.industry,
            "price_credits": template.price_credits,
        },
        tags=list(template.tags or []),
    )


async def reindex_all_templates(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(MarketplaceTemplate).where(
                MarketplaceTemplate.tenant_id == tenant_id,
                MarketplaceTemplate.status == "published",
            )
        )
    ).scalars().all()
    for row in rows:
        await index_template(session, row)
    return len(rows)


__all__ = ["index_template", "reindex_all_templates"]

