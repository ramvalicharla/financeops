from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisDataSnapshot, MisNormalizedLine
from financeops.utils.display_scale import DisplayScale, scale_report_data


_METRIC_FIELD_MAP: dict[str, str] = {
    "revenue": "revenue",
    "revenue_net": "revenue",
    "gross_profit": "gross_profit",
    "ebitda": "ebitda",
    "ebit": "ebit",
    "profit_before_tax": "profit_before_tax",
    "pbt": "profit_before_tax",
    "profit_after_tax": "profit_after_tax",
    "pat": "profit_after_tax",
    "total_assets": "total_assets",
    "assets_total": "total_assets",
    "total_liabilities": "total_liabilities",
    "liabilities_total": "total_liabilities",
    "total_equity": "total_equity",
    "equity_total": "total_equity",
    "operating_cash_flow": "operating_cash_flow",
    "free_cash_flow": "free_cash_flow",
}


async def get_mis_report_by_id(
    session: AsyncSession,
    report_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict[str, Any] | None:
    snapshot = (
        await session.execute(
            select(MisDataSnapshot).where(
                MisDataSnapshot.id == report_id,
                MisDataSnapshot.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if snapshot is None:
        return None

    lines = (
        await session.execute(
            select(MisNormalizedLine).where(
                MisNormalizedLine.snapshot_id == snapshot.id,
                MisNormalizedLine.tenant_id == tenant_id,
            )
        )
    ).scalars().all()

    report: dict[str, Any] = {
        "id": str(snapshot.id),
        "reporting_period": snapshot.reporting_period.isoformat(),
        "snapshot_status": snapshot.snapshot_status,
        "currency_code": "INR",
        "revenue": Decimal("0"),
        "gross_profit": Decimal("0"),
        "ebitda": Decimal("0"),
        "ebit": Decimal("0"),
        "profit_before_tax": Decimal("0"),
        "profit_after_tax": Decimal("0"),
        "total_assets": Decimal("0"),
        "total_liabilities": Decimal("0"),
        "total_equity": Decimal("0"),
        "operating_cash_flow": Decimal("0"),
        "free_cash_flow": Decimal("0"),
    }

    for line in lines:
        metric = (line.canonical_metric_code or "").strip().lower()
        target_field = _METRIC_FIELD_MAP.get(metric)
        if target_field is None:
            continue
        report[target_field] = Decimal(str(report[target_field])) + Decimal(str(line.period_value))
        if report.get("currency_code") in (None, "", "INR"):
            report["currency_code"] = line.currency_code

    return report


def apply_scale_to_mis_report(report: dict[str, Any], scale: DisplayScale) -> dict[str, Any]:
    amount_fields = [
        "revenue",
        "gross_profit",
        "ebitda",
        "ebit",
        "profit_before_tax",
        "profit_after_tax",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "operating_cash_flow",
        "free_cash_flow",
    ]
    return scale_report_data(report, amount_fields, scale)

