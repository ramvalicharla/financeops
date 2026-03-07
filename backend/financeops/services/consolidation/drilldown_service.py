from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.consolidation import (
    ConsolidationLineItem,
    ConsolidationRun,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount


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


def _lineage_meta(
    *,
    parent_reference_id: str | None,
    source_reference_id: str | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    return {
        "parent_reference_id": parent_reference_id,
        "source_reference_id": source_reference_id,
        "correlation_id": correlation_id,
    }


async def get_account_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    account_code: str,
) -> dict[str, Any]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    rows = (
        await session.execute(
            select(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
                ConsolidationLineItem.account_code == account_code,
            )
            .order_by(ConsolidationLineItem.entity_id, ConsolidationLineItem.id)
        )
    ).scalars().all()
    if not rows:
        raise NotFoundError("No line items found for account in this run")

    entity_bucket: dict[UUID, dict[str, Any]] = {}
    for row in rows:
        entry = entity_bucket.setdefault(
            row.entity_id,
            {
                "entity_id": str(row.entity_id),
                "local_amount_total": Decimal("0.000000"),
                "parent_amount_total": Decimal("0.000000"),
                "fx_delta_total": Decimal("0.000000"),
                "child_line_item_ids": [],
                "correlation_id": row.correlation_id,
            },
        )
        entry["local_amount_total"] = quantize_persisted_amount(
            entry["local_amount_total"] + row.local_amount
        )
        entry["parent_amount_total"] = quantize_persisted_amount(
            entry["parent_amount_total"] + row.parent_amount
        )
        entry["fx_delta_total"] = quantize_persisted_amount(
            entry["fx_delta_total"] + row.fx_delta_component
        )
        entry["child_line_item_ids"].append(str(row.id))

    entities = []
    for entity_id, payload in sorted(entity_bucket.items(), key=lambda item: str(item[0])):
        child_ids = sorted(payload["child_line_item_ids"])
        entities.append(
            {
                "entity_id": payload["entity_id"],
                "local_amount_total": str(payload["local_amount_total"]),
                "parent_amount_total": str(payload["parent_amount_total"]),
                "fx_delta_total": str(payload["fx_delta_total"]),
                "child_line_item_ids": child_ids,
                **_lineage_meta(
                    parent_reference_id=account_code,
                    source_reference_id=str(entity_id),
                    correlation_id=payload["correlation_id"],
                ),
            }
        )
    return {
        "run_id": str(run_id),
        "account_code": account_code,
        **_lineage_meta(
            parent_reference_id=str(run_id),
            source_reference_id=account_code,
            correlation_id=run.correlation_id,
        ),
        "child_entity_ids": [row["entity_id"] for row in entities],
        "entities": entities,
    }


async def get_entity_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    entity_id: UUID,
) -> dict[str, Any]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    rows = (
        await session.execute(
            select(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
                ConsolidationLineItem.entity_id == entity_id,
            )
            .order_by(ConsolidationLineItem.account_code, ConsolidationLineItem.id)
        )
    ).scalars().all()
    if not rows:
        raise NotFoundError("No line items found for entity in this run")

    line_items = [
        {
            "line_item_id": str(row.id),
            "account_code": row.account_code,
            "local_currency": row.local_currency,
            "local_amount": str(row.local_amount),
            "fx_rate_used": str(row.fx_rate_used),
            "parent_amount": str(row.parent_amount),
            "fx_delta_component": str(row.fx_delta_component),
            "child_snapshot_line_id": str(row.snapshot_line_id),
            **_lineage_meta(
                parent_reference_id=str(entity_id),
                source_reference_id=str(row.snapshot_line_id),
                correlation_id=row.correlation_id,
            ),
        }
        for row in rows
    ]
    child_ids = sorted(item["line_item_id"] for item in line_items)
    return {
        "run_id": str(run_id),
        "entity_id": str(entity_id),
        **_lineage_meta(
            parent_reference_id=str(run_id),
            source_reference_id=str(entity_id),
            correlation_id=run.correlation_id,
        ),
        "child_line_item_ids": child_ids,
        "line_items": line_items,
    }


async def get_line_item_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_item_id: UUID,
) -> dict[str, Any]:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    line_item = (
        await session.execute(
            select(ConsolidationLineItem).where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
                ConsolidationLineItem.id == line_item_id,
            )
        )
    ).scalar_one_or_none()
    if line_item is None:
        raise NotFoundError("Consolidation line item not found")

    snapshot_line = (
        await session.execute(
            select(NormalizedFinancialSnapshotLine).where(
                NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
                NormalizedFinancialSnapshotLine.id == line_item.snapshot_line_id,
            )
        )
    ).scalar_one_or_none()
    snapshot_payload = None
    if snapshot_line is not None:
        snapshot_payload = {
            "snapshot_line_id": str(snapshot_line.id),
            "snapshot_id": str(snapshot_line.snapshot_id),
            "account_code": snapshot_line.account_code,
            "local_amount": str(snapshot_line.local_amount),
            "currency": snapshot_line.currency,
            "ic_reference": snapshot_line.ic_reference,
            "counterparty_entity": (
                str(snapshot_line.counterparty_entity)
                if snapshot_line.counterparty_entity is not None
                else None
            ),
            "transaction_date": (
                snapshot_line.transaction_date.isoformat()
                if snapshot_line.transaction_date is not None
                else None
            ),
            "ic_account_class": snapshot_line.ic_account_class,
            **_lineage_meta(
                parent_reference_id=str(line_item.id),
                source_reference_id=str(snapshot_line.snapshot_id),
                correlation_id=snapshot_line.correlation_id,
            ),
        }
    return {
        "run_id": str(run_id),
        "line_item_id": str(line_item.id),
        **_lineage_meta(
            parent_reference_id=str(line_item.entity_id),
            source_reference_id=str(line_item.snapshot_line_id),
            correlation_id=line_item.correlation_id,
        ),
        "child_snapshot_line_id": str(line_item.snapshot_line_id),
        "line_item": {
            "line_item_id": str(line_item.id),
            "entity_id": str(line_item.entity_id),
            "account_code": line_item.account_code,
            "local_currency": line_item.local_currency,
            "local_amount": str(line_item.local_amount),
            "fx_rate_used": str(line_item.fx_rate_used),
            "expected_rate": str(line_item.expected_rate),
            "parent_amount": str(line_item.parent_amount),
            "fx_delta_component": str(line_item.fx_delta_component),
            "ic_reference": line_item.ic_reference,
            "ic_counterparty_entity": (
                str(line_item.ic_counterparty_entity)
                if line_item.ic_counterparty_entity is not None
                else None
            ),
            "transaction_date": (
                line_item.transaction_date.isoformat()
                if line_item.transaction_date is not None
                else None
            ),
        },
        "snapshot_line": snapshot_payload,
    }


async def get_snapshot_line_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    snapshot_line_id: UUID,
) -> dict[str, Any]:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    line_item = (
        await session.execute(
            select(ConsolidationLineItem).where(
                ConsolidationLineItem.tenant_id == tenant_id,
                ConsolidationLineItem.run_id == run_id,
                ConsolidationLineItem.snapshot_line_id == snapshot_line_id,
            )
        )
    ).scalar_one_or_none()
    if line_item is None:
        raise NotFoundError("Snapshot line is not part of this run")
    snapshot_line = (
        await session.execute(
            select(NormalizedFinancialSnapshotLine).where(
                NormalizedFinancialSnapshotLine.tenant_id == tenant_id,
                NormalizedFinancialSnapshotLine.id == snapshot_line_id,
            )
        )
    ).scalar_one_or_none()
    if snapshot_line is None:
        raise NotFoundError("Snapshot line not found")

    return {
        "run_id": str(run_id),
        "snapshot_line_id": str(snapshot_line.id),
        **_lineage_meta(
            parent_reference_id=str(line_item.id),
            source_reference_id=str(snapshot_line.snapshot_id),
            correlation_id=snapshot_line.correlation_id or line_item.correlation_id,
        ),
        "child_references": [],
        "snapshot_line": {
            "snapshot_line_id": str(snapshot_line.id),
            "snapshot_id": str(snapshot_line.snapshot_id),
            "account_code": snapshot_line.account_code,
            "local_amount": str(snapshot_line.local_amount),
            "currency": snapshot_line.currency,
            "ic_reference": snapshot_line.ic_reference,
            "counterparty_entity": (
                str(snapshot_line.counterparty_entity)
                if snapshot_line.counterparty_entity is not None
                else None
            ),
            "transaction_date": (
                snapshot_line.transaction_date.isoformat()
                if snapshot_line.transaction_date is not None
                else None
            ),
            "ic_account_class": snapshot_line.ic_account_class,
        },
    }
