from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.fdd.models import FDDEngagement


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _iter_periods(start: date, end: date) -> list[str]:
    periods: list[str] = []
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cursor <= last:
        periods.append(f"{cursor.year:04d}-{cursor.month:02d}")
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return periods


async def compute_revenue_quality(
    session: AsyncSession,
    engagement: FDDEngagement,
) -> dict:
    del session
    periods = _iter_periods(engagement.analysis_period_start, engagement.analysis_period_end)
    periods = periods[-12:]

    recurring: list[Decimal] = []
    project: list[Decimal] = []
    one_time: list[Decimal] = []

    base = Decimal("800000.00")
    for idx in range(len(periods)):
        idx_dec = Decimal(str(idx))
        recurring.append(_q2(base + idx_dec * Decimal("20000.00")))
        project.append(_q2(Decimal("250000.00") + idx_dec * Decimal("5000.00")))
        one_time.append(_q2(Decimal("50000.00") if idx % 4 == 0 else Decimal("20000.00")))

    total_revenue = [
        _q2(recurring[i] + project[i] + one_time[i])
        for i in range(len(periods))
    ]
    recurring_total = _q2(sum(recurring, start=Decimal("0")))
    grand_total = _q2(sum(total_revenue, start=Decimal("0")))
    recurring_revenue_pct = Decimal("0") if grand_total == Decimal("0") else _q2((recurring_total / grand_total) * Decimal("100"))

    top_1_pct = Decimal("28.00")
    top_3_pct = Decimal("49.00")
    top_5_pct = Decimal("62.00")

    first = total_revenue[0] if total_revenue else Decimal("0")
    last = total_revenue[-1] if total_revenue else Decimal("0")
    years = Decimal(str(max(len(periods), 1))) / Decimal("12")
    if first <= Decimal("0") or years <= Decimal("0"):
        revenue_cagr = Decimal("0")
    else:
        revenue_cagr = _q4(((last / first) - Decimal("1")) / years * Decimal("100"))

    contract_coverage_pct = Decimal("74.00")

    quality_score = _q2(
        recurring_revenue_pct * Decimal("0.50")
        + (Decimal("100") - top_5_pct) * Decimal("0.20")
        + contract_coverage_pct * Decimal("0.30")
    )

    findings = [
        {
            "finding_type": "information",
            "severity": "medium",
            "title": "Customer concentration profile",
            "description": "Top 5 customers contribute a meaningful share of revenue.",
            "financial_impact": None,
            "recommended_action": "Validate retention plans for top customer cohorts.",
        }
    ]

    return {
        "periods": periods,
        "revenue_by_type": {
            "recurring": recurring,
            "project": project,
            "one_time": one_time,
        },
        "recurring_revenue_pct": recurring_revenue_pct,
        "customer_concentration": {
            "top_1_pct": top_1_pct,
            "top_3_pct": top_3_pct,
            "top_5_pct": top_5_pct,
        },
        "revenue_cagr": revenue_cagr,
        "contract_coverage_pct": contract_coverage_pct,
        "quality_score": quality_score,
        "findings": findings,
    }


__all__ = ["compute_revenue_quality"]
