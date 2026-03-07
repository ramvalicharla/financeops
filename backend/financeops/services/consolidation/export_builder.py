from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationLineItem,
    ConsolidationResult,
    IntercompanyPair,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.consolidation.excel_exporter import build_consolidation_excel
from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount
from financeops.services.consolidation.lineage_links import resolve_pair_line_item_links


async def build_export_workbook(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    parent_currency: str,
) -> tuple[bytes, str]:
    result_rows = (
        await session.execute(
            select(ConsolidationResult)
            .where(
                ConsolidationResult.tenant_id == tenant_id,
                ConsolidationResult.run_id == run_id,
            )
            .order_by(ConsolidationResult.consolidated_account_code)
        )
    ).scalars().all()
    line_rows = (
        await session.execute(
            select(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
            )
            .order_by(
                ConsolidationLineItem.entity_id,
                ConsolidationLineItem.account_code,
                ConsolidationLineItem.id,
            )
        )
    ).scalars().all()
    pair_rows = (
        await session.execute(
            select(IntercompanyPair)
            .where(
                IntercompanyPair.tenant_id == tenant_id,
                IntercompanyPair.run_id == run_id,
            )
            .order_by(IntercompanyPair.match_key_hash)
        )
    ).scalars().all()
    elimination_rows = (
        await session.execute(
            select(ConsolidationElimination)
            .where(
                ConsolidationElimination.tenant_id == tenant_id,
                ConsolidationElimination.run_id == run_id,
            )
            .order_by(ConsolidationElimination.id)
        )
    ).scalars().all()

    snapshot_ids = sorted({row.snapshot_line_id for row in line_rows}, key=str)
    snapshot_rows: list[NormalizedFinancialSnapshotLine] = []
    snapshot_headers_by_id: dict[UUID, NormalizedFinancialSnapshot] = {}
    if snapshot_ids:
        snapshot_rows = (
            await session.execute(
                select(NormalizedFinancialSnapshotLine)
                .where(
                    NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
                    NormalizedFinancialSnapshotLine.id.in_(snapshot_ids),
                )
                .order_by(
                    NormalizedFinancialSnapshotLine.snapshot_id,
                    NormalizedFinancialSnapshotLine.id,
                )
            )
        ).scalars().all()
        header_ids = sorted({row.snapshot_id for row in snapshot_rows}, key=str)
        if header_ids:
            headers = (
                await session.execute(
                    select(NormalizedFinancialSnapshot).where(
                        NormalizedFinancialSnapshot.tenant_id == tenant_id,
                        NormalizedFinancialSnapshot.id.in_(header_ids),
                    )
                )
            ).scalars().all()
            snapshot_headers_by_id = {row.id: row for row in headers}

    pair_links = resolve_pair_line_item_links(
        pairs=list(pair_rows),
        line_items=list(line_rows),
    )

    entity_bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for row in line_rows:
        key = (row.account_code, str(row.entity_id))
        bucket = entity_bucket.setdefault(
            key,
            {
                "account_code": row.account_code,
                "entity_id": str(row.entity_id),
                "local_amount_total": Decimal("0.000000"),
                "parent_amount_total": Decimal("0.000000"),
                "fx_impact_total": Decimal("0.000000"),
                "correlation_id": row.correlation_id,
            },
        )
        bucket["local_amount_total"] = quantize_persisted_amount(
            bucket["local_amount_total"] + row.local_amount
        )
        bucket["parent_amount_total"] = quantize_persisted_amount(
            bucket["parent_amount_total"] + row.parent_amount
        )
        bucket["fx_impact_total"] = quantize_persisted_amount(
            bucket["fx_impact_total"] + row.fx_delta_component
        )

    return build_consolidation_excel(
        parent_currency=parent_currency,
        consolidated_rows=[
            {
                "consolidated_result_id": row.id,
                "account_code": row.consolidated_account_code,
                "consolidated_amount_parent": row.consolidated_amount_parent,
                "fx_impact_total": row.fx_impact_total,
                "correlation_id": row.correlation_id,
            }
            for row in result_rows
        ],
        entity_rows=[
            row for _, row in sorted(entity_bucket.items(), key=lambda item: (item[0][0], item[0][1]))
        ],
        line_item_rows=[
            {
                "line_item_id": row.id,
                "entity_id": row.entity_id,
                "account_code": row.account_code,
                "local_currency": row.local_currency,
                "local_amount": row.local_amount,
                "fx_rate_used": row.fx_rate_used,
                "parent_amount": row.parent_amount,
                "fx_delta_component": row.fx_delta_component,
                "snapshot_line_id": row.snapshot_line_id,
                "correlation_id": row.correlation_id,
            }
            for row in line_rows
        ],
        intercompany_rows=[
            {
                "pair_id": row.id,
                "entity_from": row.entity_from,
                "entity_to": row.entity_to,
                "account_code": row.account_code,
                "classification": row.classification,
                "actual_difference": row.actual_difference,
                "unexplained_difference": row.unexplained_difference,
                "line_item_from_id": pair_links.get(row.id).line_item_from_id
                if row.id in pair_links
                else None,
                "line_item_to_id": pair_links.get(row.id).line_item_to_id
                if row.id in pair_links
                else None,
                "correlation_id": row.correlation_id,
            }
            for row in pair_rows
        ],
        elimination_rows=[
            {
                "elimination_id": row.id,
                "intercompany_pair_id": row.intercompany_pair_id,
                "elimination_status": row.elimination_status,
                "eliminated_amount_parent": row.eliminated_amount_parent,
                "fx_component_impact_parent": row.fx_component_impact_parent,
                "residual_difference_parent": row.residual_difference_parent,
                "rule_code": row.rule_code,
                "reason": row.reason,
                "correlation_id": row.correlation_id,
            }
            for row in elimination_rows
        ],
        unexplained_rows=[
            {
                "pair_id": row.id,
                "entity_from": row.entity_from,
                "entity_to": row.entity_to,
                "account_code": row.account_code,
                "classification": row.classification,
                "expected_difference": row.expected_difference,
                "actual_difference": row.actual_difference,
                "fx_explained": row.fx_explained,
                "unexplained_difference": row.unexplained_difference,
                "transaction_date_from": None,
                "transaction_date_to": None,
            }
            for row in pair_rows
            if row.classification in {"timing_difference", "unexplained"}
        ],
        snapshot_rows=[
            {
                "snapshot_line_id": row.id,
                "snapshot_id": row.snapshot_id,
                "entity_id": (
                    snapshot_headers_by_id[row.snapshot_id].entity_id
                    if row.snapshot_id in snapshot_headers_by_id
                    else ""
                ),
                "account_code": row.account_code,
                "currency": row.currency,
                "local_amount": row.local_amount,
                "ic_reference": row.ic_reference,
                "counterparty_entity": row.counterparty_entity,
                "transaction_date": row.transaction_date,
                "ic_account_class": row.ic_account_class,
                "source_artifact_reference": (
                    snapshot_headers_by_id[row.snapshot_id].source_artifact_reference
                    if row.snapshot_id in snapshot_headers_by_id
                    else ""
                ),
            }
            for row in snapshot_rows
        ],
    )
