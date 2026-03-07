from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationLineItem,
    ConsolidationResult,
    IntercompanyPair,
)
from financeops.services.consolidation.export_builder import build_export_workbook
from financeops.services.consolidation.run_events import get_latest_run_event
from financeops.services.consolidation.run_store import get_run_or_raise
from financeops.services.consolidation.service_types import ExportPayload
from financeops.services.consolidation.fx_impact_calculator import quantize_persisted_amount


async def get_run_status(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    event = await get_latest_run_event(session, tenant_id=tenant_id, run_id=run_id)
    return {
        "run_id": str(run_id),
        "status": event.event_type,
        "event_seq": event.event_seq,
        "event_time": event.event_time,
        "metadata": event.metadata_json,
    }


async def list_results(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    result = await session.execute(
        select(ConsolidationResult)
        .where(
            ConsolidationResult.tenant_id == tenant_id,
            ConsolidationResult.run_id == run_id,
        )
        .order_by(ConsolidationResult.consolidated_account_code)
    )
    rows = list(result.scalars().all())
    total_amount = quantize_persisted_amount(
        sum((row.consolidated_amount_parent for row in rows), start=Decimal("0.000000"))
    )
    total_fx = quantize_persisted_amount(
        sum((row.fx_impact_total for row in rows), start=Decimal("0.000000"))
    )
    return {
        "run_id": str(run_id),
        "parent_currency": run.parent_currency,
        "rows": [
            {
                "consolidated_account_code": row.consolidated_account_code,
                "consolidated_amount_parent": str(row.consolidated_amount_parent),
                "fx_impact_total": str(row.fx_impact_total),
            }
            for row in rows
        ],
        "count": len(rows),
        "total_consolidated_amount_parent": str(total_amount),
        "total_fx_impact_parent": str(total_fx),
    }


async def list_ic_differences(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    rows_result = await session.execute(
        select(IntercompanyPair)
        .where(
            IntercompanyPair.tenant_id == tenant_id,
            IntercompanyPair.run_id == run_id,
        )
        .order_by(IntercompanyPair.match_key_hash)
    )
    rows = list(rows_result.scalars().all())
    date_map_result = await session.execute(
        select(
            ConsolidationLineItem.ic_reference,
            ConsolidationLineItem.entity_id,
            ConsolidationLineItem.transaction_date,
            ConsolidationLineItem.account_code,
        ).where(
            ConsolidationLineItem.tenant_id == tenant_id,
            ConsolidationLineItem.run_id == run_id,
        )
    )
    tx_date_map: dict[tuple[str | None, UUID, str], date | None] = {}
    for ic_reference, entity_id, transaction_date, account_code in date_map_result.all():
        tx_date_map[(ic_reference, entity_id, account_code)] = transaction_date

    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        payload_rows.append(
            {
                "pair_id": str(row.id),
                "entity_from": str(row.entity_from),
                "entity_to": str(row.entity_to),
                "account_code": row.account_code,
                "ic_reference": row.ic_reference,
                "classification": row.classification,
                "expected_difference": str(row.expected_difference),
                "actual_difference": str(row.actual_difference),
                "fx_explained": str(row.fx_explained),
                "unexplained_difference": str(row.unexplained_difference),
                "transaction_date_from": tx_date_map.get(
                    (row.ic_reference, row.entity_from, row.account_code)
                ),
                "transaction_date_to": tx_date_map.get(
                    (row.ic_reference, row.entity_to, row.account_code)
                ),
            }
        )
    return {"run_id": str(run_id), "rows": payload_rows, "count": len(payload_rows)}


async def build_export(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> ExportPayload:
    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    workbook_bytes, checksum = await build_export_workbook(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        parent_currency=run.parent_currency,
    )
    return ExportPayload(workbook_bytes=workbook_bytes, checksum=checksum)
