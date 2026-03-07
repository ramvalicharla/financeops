from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationLineItem,
    IntercompanyPair,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.consolidation.lineage_links import resolve_pair_line_item_links


@dataclass(frozen=True)
class LineageValidationResult:
    is_complete: bool
    missing_snapshot_line_links: int
    missing_elimination_pair_links: int
    missing_intercompany_line_links: int

    def as_metadata(self) -> dict[str, int | str]:
        return {
            "error_code": "LINEAGE_INCOMPLETE",
            "missing_snapshot_line_links": self.missing_snapshot_line_links,
            "missing_elimination_pair_links": self.missing_elimination_pair_links,
            "missing_intercompany_line_links": self.missing_intercompany_line_links,
        }


async def validate_lineage_completeness(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    missing_snapshot_line_links = int(
        await session.scalar(
            select(func.count())
            .select_from(ConsolidationLineItem)
            .outerjoin(
                NormalizedFinancialSnapshotLine,
                ConsolidationLineItem.snapshot_line_id == NormalizedFinancialSnapshotLine.id,
            )
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
                NormalizedFinancialSnapshotLine.id.is_(None),
            )
        )
        or 0
    )

    missing_elimination_pair_links = int(
        await session.scalar(
            select(func.count())
            .select_from(ConsolidationElimination)
            .outerjoin(
                IntercompanyPair,
                ConsolidationElimination.intercompany_pair_id == IntercompanyPair.id,
            )
            .where(
                ConsolidationElimination.tenant_id == tenant_id,
                ConsolidationElimination.run_id == run_id,
                IntercompanyPair.id.is_(None),
            )
        )
        or 0
    )

    pairs = (
        await session.execute(
            select(IntercompanyPair).where(
                IntercompanyPair.tenant_id == tenant_id,
                IntercompanyPair.run_id == run_id,
            )
        )
    ).scalars().all()
    line_items = (
        await session.execute(
            select(ConsolidationLineItem).where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
            )
        )
    ).scalars().all()
    pair_links = resolve_pair_line_item_links(
        pairs=list(pairs),
        line_items=list(line_items),
    )
    missing_intercompany_line_links = sum(
        1
        for pair in pairs
        if (
            pair.id not in pair_links
            or pair_links[pair.id].line_item_from_id is None
            or pair_links[pair.id].line_item_to_id is None
        )
    )

    is_complete = (
        missing_snapshot_line_links == 0
        and missing_elimination_pair_links == 0
        and missing_intercompany_line_links == 0
    )
    return LineageValidationResult(
        is_complete=is_complete,
        missing_snapshot_line_links=missing_snapshot_line_links,
        missing_elimination_pair_links=missing_elimination_pair_links,
        missing_intercompany_line_links=missing_intercompany_line_links,
    )
