from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationLineItem,
    ConsolidationResult,
    ConsolidationRun,
    IntercompanyPair,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.consolidation.lineage_links import resolve_pair_line_item_links

LineageRecordType = Literal[
    "consolidation_result",
    "consolidation_line_item",
    "intercompany_pair",
    "elimination",
    "snapshot_line",
]


def _lineage_node(
    *,
    record_type: str,
    record_id: UUID | str,
    parent_record_type: str | None,
    parent_record_id: UUID | str | None,
    foreign_key_path: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    return {
        "record_type": record_type,
        "record_id": str(record_id),
        "parent_record_type": parent_record_type,
        "parent_record_id": str(parent_record_id) if parent_record_id is not None else None,
        "foreign_key_path": foreign_key_path,
        "correlation_id": correlation_id,
    }


async def _get_run_or_raise(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> ConsolidationRun:
    run = (
        await session.execute(
            select(ConsolidationRun).where(
                ConsolidationRun.tenant_id == tenant_id,
                ConsolidationRun.id == run_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Consolidation run not found")
    return run


async def _resolve_result_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    result = (
        await session.execute(
            select(ConsolidationResult).where(
                ConsolidationResult.tenant_id == tenant_id,
                ConsolidationResult.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if result is None:
        raise NotFoundError("Consolidation result not found")
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=result.run_id)
    line_items = (
        await session.execute(
            select(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == result.run_id,
                ConsolidationLineItem.account_code == result.consolidated_account_code,
            )
            .order_by(ConsolidationLineItem.entity_id, ConsolidationLineItem.id)
        )
    ).scalars().all()

    ancestry: list[dict[str, Any]] = [
        _lineage_node(
            record_type="consolidation_run",
            record_id=run.id,
            parent_record_type=None,
            parent_record_id=None,
            foreign_key_path="root",
            correlation_id=run.correlation_id,
        ),
        _lineage_node(
            record_type="consolidation_result",
            record_id=result.id,
            parent_record_type="consolidation_run",
            parent_record_id=run.id,
            foreign_key_path="consolidation_results.run_id -> consolidation_runs.id",
            correlation_id=result.correlation_id,
        ),
    ]
    for line in line_items:
        ancestry.append(
            _lineage_node(
                record_type="consolidation_line_item",
                record_id=line.id,
                parent_record_type="consolidation_result",
                parent_record_id=result.id,
                foreign_key_path="account_code + run_id logical lineage",
                correlation_id=line.correlation_id,
            )
        )
        ancestry.append(
            _lineage_node(
                record_type="snapshot_line",
                record_id=line.snapshot_line_id,
                parent_record_type="consolidation_line_item",
                parent_record_id=line.id,
                foreign_key_path=(
                    "consolidation_line_items.snapshot_line_id "
                    "-> normalized_financial_snapshot_lines.snapshot_line_id"
                ),
                correlation_id=line.correlation_id,
            )
        )
    return {
        "record_type": "consolidation_result",
        "record_id": str(result.id),
        "correlation_id": result.correlation_id,
        "ancestry": ancestry,
    }


async def _resolve_line_item_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    line_item = (
        await session.execute(
            select(ConsolidationLineItem).where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if line_item is None:
        raise NotFoundError("Consolidation line item not found")
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=line_item.run_id)
    snapshot_line = (
        await session.execute(
            select(NormalizedFinancialSnapshotLine).where(
                NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
                NormalizedFinancialSnapshotLine.id == line_item.snapshot_line_id,
            )
        )
    ).scalar_one_or_none()
    snapshot_header = None
    if snapshot_line is not None:
        snapshot_header = (
            await session.execute(
                select(NormalizedFinancialSnapshot).where(
                    NormalizedFinancialSnapshot.tenant_id == tenant_id,
                    NormalizedFinancialSnapshot.id == snapshot_line.snapshot_id,
                )
            )
        ).scalar_one_or_none()

    ancestry = [
        _lineage_node(
            record_type="consolidation_run",
            record_id=run.id,
            parent_record_type=None,
            parent_record_id=None,
            foreign_key_path="root",
            correlation_id=run.correlation_id,
        ),
        _lineage_node(
            record_type="consolidation_line_item",
            record_id=line_item.id,
            parent_record_type="consolidation_run",
            parent_record_id=run.id,
            foreign_key_path="consolidation_line_items.run_id -> consolidation_runs.id",
            correlation_id=line_item.correlation_id,
        ),
    ]
    if snapshot_line is not None:
        ancestry.append(
            _lineage_node(
                record_type="snapshot_line",
                record_id=snapshot_line.id,
                parent_record_type="consolidation_line_item",
                parent_record_id=line_item.id,
                foreign_key_path=(
                    "consolidation_line_items.snapshot_line_id "
                    "-> normalized_financial_snapshot_lines.snapshot_line_id"
                ),
                correlation_id=snapshot_line.correlation_id,
            )
        )
    if snapshot_header is not None:
        ancestry.append(
            _lineage_node(
                record_type="snapshot",
                record_id=snapshot_header.id,
                parent_record_type="snapshot_line",
                parent_record_id=snapshot_line.id if snapshot_line is not None else None,
                foreign_key_path=(
                    "normalized_financial_snapshot_lines.snapshot_id "
                    "-> normalized_financial_snapshots.snapshot_id"
                ),
                correlation_id=snapshot_header.correlation_id,
            )
        )
    return {
        "record_type": "consolidation_line_item",
        "record_id": str(line_item.id),
        "correlation_id": line_item.correlation_id,
        "ancestry": ancestry,
    }


async def _resolve_intercompany_pair_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    pair = (
        await session.execute(
            select(IntercompanyPair).where(
                IntercompanyPair.tenant_id == tenant_id,
                IntercompanyPair.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if pair is None:
        raise NotFoundError("Intercompany pair not found")
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=pair.run_id)
    line_items = (
        await session.execute(
            select(ConsolidationLineItem).where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == pair.run_id,
            )
        )
    ).scalars().all()
    links = resolve_pair_line_item_links(pairs=[pair], line_items=list(line_items))
    link = links[pair.id]

    ancestry = [
        _lineage_node(
            record_type="consolidation_run",
            record_id=run.id,
            parent_record_type=None,
            parent_record_id=None,
            foreign_key_path="root",
            correlation_id=run.correlation_id,
        ),
        _lineage_node(
            record_type="intercompany_pair",
            record_id=pair.id,
            parent_record_type="consolidation_run",
            parent_record_id=run.id,
            foreign_key_path="intercompany_pairs.run_id -> consolidation_runs.id",
            correlation_id=pair.correlation_id,
        ),
    ]
    if link.line_item_from_id is not None:
        ancestry.append(
            _lineage_node(
                record_type="consolidation_line_item",
                record_id=link.line_item_from_id,
                parent_record_type="intercompany_pair",
                parent_record_id=pair.id,
                foreign_key_path="deterministic IC lineage (entity_from)",
                correlation_id=pair.correlation_id,
            )
        )
    if link.line_item_to_id is not None:
        ancestry.append(
            _lineage_node(
                record_type="consolidation_line_item",
                record_id=link.line_item_to_id,
                parent_record_type="intercompany_pair",
                parent_record_id=pair.id,
                foreign_key_path="deterministic IC lineage (entity_to)",
                correlation_id=pair.correlation_id,
            )
        )
    return {
        "record_type": "intercompany_pair",
        "record_id": str(pair.id),
        "correlation_id": pair.correlation_id,
        "ancestry": ancestry,
    }


async def _resolve_elimination_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    elimination = (
        await session.execute(
            select(ConsolidationElimination).where(
                ConsolidationElimination.tenant_id == tenant_id,
                ConsolidationElimination.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if elimination is None:
        raise NotFoundError("Consolidation elimination not found")
    pair = (
        await session.execute(
            select(IntercompanyPair).where(
                IntercompanyPair.tenant_id == tenant_id,
                IntercompanyPair.id == elimination.intercompany_pair_id,
            )
        )
    ).scalar_one_or_none()
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=elimination.run_id)
    ancestry = [
        _lineage_node(
            record_type="consolidation_run",
            record_id=run.id,
            parent_record_type=None,
            parent_record_id=None,
            foreign_key_path="root",
            correlation_id=run.correlation_id,
        ),
        _lineage_node(
            record_type="intercompany_pair",
            record_id=pair.id if pair is not None else elimination.intercompany_pair_id,
            parent_record_type="consolidation_run",
            parent_record_id=run.id,
            foreign_key_path="intercompany_pairs.run_id -> consolidation_runs.id",
            correlation_id=pair.correlation_id if pair is not None else elimination.correlation_id,
        ),
        _lineage_node(
            record_type="elimination",
            record_id=elimination.id,
            parent_record_type="intercompany_pair",
            parent_record_id=elimination.intercompany_pair_id,
            foreign_key_path=(
                "consolidation_eliminations.intercompany_pair_id -> intercompany_pairs.id"
            ),
            correlation_id=elimination.correlation_id,
        ),
    ]
    return {
        "record_type": "elimination",
        "record_id": str(elimination.id),
        "correlation_id": elimination.correlation_id,
        "ancestry": ancestry,
    }


async def _resolve_snapshot_line_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    snapshot_line = (
        await session.execute(
            select(NormalizedFinancialSnapshotLine).where(
                NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
                NormalizedFinancialSnapshotLine.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if snapshot_line is None:
        raise NotFoundError("Snapshot line not found")
    snapshot = (
        await session.execute(
            select(NormalizedFinancialSnapshot).where(
                NormalizedFinancialSnapshot.tenant_id == tenant_id,
                NormalizedFinancialSnapshot.id == snapshot_line.snapshot_id,
            )
        )
    ).scalar_one_or_none()
    line_items = (
        await session.execute(
            select(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.snapshot_line_id == snapshot_line.id,
            )
            .order_by(ConsolidationLineItem.run_id, ConsolidationLineItem.id)
        )
    ).scalars().all()

    ancestry: list[dict[str, Any]] = [
        _lineage_node(
            record_type="snapshot",
            record_id=snapshot.id if snapshot is not None else snapshot_line.snapshot_id,
            parent_record_type=None,
            parent_record_id=None,
            foreign_key_path="root",
            correlation_id=snapshot.correlation_id if snapshot is not None else None,
        ),
        _lineage_node(
            record_type="snapshot_line",
            record_id=snapshot_line.id,
            parent_record_type="snapshot",
            parent_record_id=snapshot_line.snapshot_id,
            foreign_key_path=(
                "normalized_financial_snapshot_lines.snapshot_id "
                "-> normalized_financial_snapshots.snapshot_id"
            ),
            correlation_id=snapshot_line.correlation_id,
        ),
    ]
    for line_item in line_items:
        ancestry.append(
            _lineage_node(
                record_type="consolidation_line_item",
                record_id=line_item.id,
                parent_record_type="snapshot_line",
                parent_record_id=snapshot_line.id,
                foreign_key_path=(
                    "consolidation_line_items.snapshot_line_id "
                    "-> normalized_financial_snapshot_lines.snapshot_line_id"
                ),
                correlation_id=line_item.correlation_id,
            )
        )
    return {
        "record_type": "snapshot_line",
        "record_id": str(snapshot_line.id),
        "correlation_id": snapshot_line.correlation_id,
        "ancestry": ancestry,
    }


async def resolve_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    record_type: LineageRecordType | str,
    record_id: UUID,
) -> dict[str, Any]:
    kind = str(record_type)
    if kind == "consolidation_result":
        return await _resolve_result_lineage(session, tenant_id=tenant_id, record_id=record_id)
    if kind == "consolidation_line_item":
        return await _resolve_line_item_lineage(session, tenant_id=tenant_id, record_id=record_id)
    if kind == "intercompany_pair":
        return await _resolve_intercompany_pair_lineage(
            session,
            tenant_id=tenant_id,
            record_id=record_id,
        )
    if kind == "elimination":
        return await _resolve_elimination_lineage(session, tenant_id=tenant_id, record_id=record_id)
    if kind == "snapshot_line":
        return await _resolve_snapshot_line_lineage(session, tenant_id=tenant_id, record_id=record_id)
    raise ValidationError(
        "Unsupported lineage record_type; expected one of "
        "consolidation_result, consolidation_line_item, intercompany_pair, elimination, snapshot_line"
    )

