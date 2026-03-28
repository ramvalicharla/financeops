from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_notifications import AccountingAPAgeingSnapshot


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else "0"))


async def create_ap_ageing_snapshot(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    snapshot_date: date,
    fiscal_year: int,
    fiscal_period: int,
    connector_type: str,
    vendor_buckets: list[dict[str, Any]],
) -> list[AccountingAPAgeingSnapshot]:
    snapshots: list[AccountingAPAgeingSnapshot] = []

    for bucket in vendor_buckets:
        current = _to_decimal(bucket.get("current"))
        overdue_1_30 = _to_decimal(bucket.get("overdue_1_30"))
        overdue_31_60 = _to_decimal(bucket.get("overdue_31_60"))
        overdue_61_90 = _to_decimal(bucket.get("overdue_61_90"))
        overdue_90_plus = _to_decimal(bucket.get("overdue_90_plus"))
        total_outstanding = (
            current
            + overdue_1_30
            + overdue_31_60
            + overdue_61_90
            + overdue_90_plus
        )

        vendor_id_raw = bucket.get("vendor_id")
        vendor_id = (
            vendor_id_raw
            if isinstance(vendor_id_raw, uuid.UUID) or vendor_id_raw is None
            else uuid.UUID(str(vendor_id_raw))
        )

        snapshot = AccountingAPAgeingSnapshot(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            chain_hash="",
            previous_hash="",
            entity_id=entity_id,
            vendor_id=vendor_id,
            snapshot_date=snapshot_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            current_amount=current,
            overdue_1_30=overdue_1_30,
            overdue_31_60=overdue_31_60,
            overdue_61_90=overdue_61_90,
            overdue_90_plus=overdue_90_plus,
            total_outstanding=total_outstanding,
            currency=str(bucket.get("currency") or "INR"),
            data_source="ERP_PULL",
            connector_type=connector_type,
            raw_data=bucket.get("raw_data"),
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    await db.flush()
    return snapshots


async def get_ap_ageing_summary(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    snapshot_date: date,
    vendor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(AccountingAPAgeingSnapshot).where(
        AccountingAPAgeingSnapshot.tenant_id == tenant_id,
        AccountingAPAgeingSnapshot.entity_id == entity_id,
        AccountingAPAgeingSnapshot.snapshot_date == snapshot_date,
    )
    if vendor_id is not None:
        stmt = stmt.where(AccountingAPAgeingSnapshot.vendor_id == vendor_id)

    rows = list((await db.execute(stmt)).scalars().all())
    totals = {
        "current": Decimal("0"),
        "overdue_1_30": Decimal("0"),
        "overdue_31_60": Decimal("0"),
        "overdue_61_90": Decimal("0"),
        "overdue_90_plus": Decimal("0"),
        "total_outstanding": Decimal("0"),
    }

    for row in rows:
        totals["current"] += row.current_amount
        totals["overdue_1_30"] += row.overdue_1_30
        totals["overdue_31_60"] += row.overdue_31_60
        totals["overdue_61_90"] += row.overdue_61_90
        totals["overdue_90_plus"] += row.overdue_90_plus
        totals["total_outstanding"] += row.total_outstanding

    return {
        "snapshot_date": str(snapshot_date),
        "entity_id": str(entity_id),
        "vendor_count": len(rows),
        **{key: str(value) for key, value in totals.items()},
    }


async def export_ap_ageing_csv(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    date_from: date,
    date_to: date,
    vendor_id: uuid.UUID | None = None,
) -> str:
    stmt = (
        select(AccountingAPAgeingSnapshot)
        .where(
            AccountingAPAgeingSnapshot.tenant_id == tenant_id,
            AccountingAPAgeingSnapshot.entity_id == entity_id,
            AccountingAPAgeingSnapshot.snapshot_date >= date_from,
            AccountingAPAgeingSnapshot.snapshot_date <= date_to,
        )
        .order_by(AccountingAPAgeingSnapshot.snapshot_date.asc())
    )
    if vendor_id is not None:
        stmt = stmt.where(AccountingAPAgeingSnapshot.vendor_id == vendor_id)

    rows = list((await db.execute(stmt)).scalars().all())

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "snapshot_date",
            "vendor_id",
            "current_amount",
            "overdue_1_30",
            "overdue_31_60",
            "overdue_61_90",
            "overdue_90_plus",
            "total_outstanding",
            "currency",
            "data_source",
            "connector_type",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "snapshot_date": str(row.snapshot_date),
                "vendor_id": str(row.vendor_id) if row.vendor_id else "",
                "current_amount": str(row.current_amount),
                "overdue_1_30": str(row.overdue_1_30),
                "overdue_31_60": str(row.overdue_31_60),
                "overdue_61_90": str(row.overdue_61_90),
                "overdue_90_plus": str(row.overdue_90_plus),
                "total_outstanding": str(row.total_outstanding),
                "currency": row.currency,
                "data_source": row.data_source,
                "connector_type": row.connector_type or "",
            }
        )
    return output.getvalue()

