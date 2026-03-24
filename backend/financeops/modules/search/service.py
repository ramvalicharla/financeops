from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.search.models import SearchIndexEntry


async def upsert_index_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    title: str,
    subtitle: str | None,
    body: str | None,
    url: str,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> SearchIndexEntry:
    table = SearchIndexEntry.__table__
    stmt = insert(table).values(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        subtitle=subtitle,
        body=body,
        tags=list(tags or []),
        url=url,
        metadata=metadata or {},
        indexed_at=datetime.now(UTC),
        is_active=True,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_search_index_entries_entity",
        set_={
            "title": title,
            "subtitle": subtitle,
            "body": body,
            "tags": list(tags or []),
            "url": url,
            "metadata": metadata or {},
            "indexed_at": datetime.now(UTC),
            "is_active": True,
        },
    )
    await session.execute(stmt)
    row = (
        await session.execute(
            select(SearchIndexEntry).where(
                SearchIndexEntry.tenant_id == tenant_id,
                SearchIndexEntry.entity_type == entity_type,
                SearchIndexEntry.entity_id == entity_id,
            )
        )
    ).scalar_one()
    await session.flush()
    return row


def _serialize_result(entry: SearchIndexEntry, rank: float) -> dict:
    return {
        "entity_type": entry.entity_type,
        "entity_id": str(entry.entity_id),
        "title": entry.title,
        "subtitle": entry.subtitle,
        "url": entry.url,
        "metadata": entry.metadata_json or {},
        "rank": float(rank),
    }


async def search(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    entity_types: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    clean_query = str(query or "").strip()
    safe_limit = max(1, min(20, int(limit)))

    if len(clean_query) < 2:
        rows = (
            await session.execute(
                select(SearchIndexEntry)
                .where(
                    SearchIndexEntry.tenant_id == tenant_id,
                    SearchIndexEntry.is_active.is_(True),
                    SearchIndexEntry.entity_type.in_(entity_types) if entity_types else True,
                )
                .order_by(desc(SearchIndexEntry.indexed_at), desc(SearchIndexEntry.id))
                .limit(safe_limit)
            )
        ).scalars().all()
        return [_serialize_result(row, rank=1.0) for row in rows]

    content = (
        SearchIndexEntry.title
        + " "
        + func.coalesce(SearchIndexEntry.subtitle, "")
        + " "
        + func.coalesce(SearchIndexEntry.body, "")
    )
    tsvector = func.to_tsvector("english", content)
    tsquery = func.plainto_tsquery("english", clean_query)
    rank_col = func.ts_rank(tsvector, tsquery).label("rank")

    stmt = (
        select(SearchIndexEntry, rank_col)
        .where(
            SearchIndexEntry.tenant_id == tenant_id,
            SearchIndexEntry.is_active.is_(True),
            tsvector.op("@@")(tsquery),
        )
        .order_by(desc(rank_col), desc(SearchIndexEntry.indexed_at), desc(SearchIndexEntry.id))
        .limit(safe_limit)
    )
    if entity_types:
        stmt = stmt.where(SearchIndexEntry.entity_type.in_(entity_types))

    rows = (await session.execute(stmt)).all()
    return [_serialize_result(entry, rank) for entry, rank in rows]


async def reindex_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    from financeops.modules.search.indexers.anomaly_indexer import reindex_all_anomalies
    from financeops.modules.search.indexers.checklist_indexer import reindex_all_checklist_tasks
    from financeops.modules.search.indexers.expense_indexer import reindex_all_expenses
    from financeops.modules.search.indexers.fdd_indexer import reindex_all_fdd
    from financeops.modules.search.indexers.mis_indexer import reindex_all_mis_lines
    from financeops.modules.search.indexers.template_indexer import reindex_all_templates

    results = {
        "expense_claim": await reindex_all_expenses(session, tenant_id),
        "anomaly": await reindex_all_anomalies(session, tenant_id),
        "checklist_task": await reindex_all_checklist_tasks(session, tenant_id),
        "fdd_engagement": await reindex_all_fdd(session, tenant_id),
        "marketplace_template": await reindex_all_templates(session, tenant_id),
        "mis_line": await reindex_all_mis_lines(session, tenant_id),
    }
    return results


__all__ = ["reindex_tenant", "search", "upsert_index_entry"]
