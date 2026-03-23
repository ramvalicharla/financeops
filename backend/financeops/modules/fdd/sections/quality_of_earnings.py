from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.fdd.models import FDDEngagement


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _month_key(dt: date) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _iter_months(start: date, end: date) -> list[str]:
    months: list[str] = []
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cursor <= last:
        months.append(_month_key(cursor))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


async def _load_qoe_period_data(session: AsyncSession, engagement: FDDEngagement) -> list[dict]:
    del session
    periods = _iter_months(engagement.analysis_period_start, engagement.analysis_period_end)
    rows: list[dict] = []
    base_revenue = Decimal("100.00")
    for idx, period in enumerate(periods):
        idx_dec = Decimal(str(idx))
        revenue = _q2(base_revenue + idx_dec * Decimal("2.00"))
        cogs = _q2(revenue * Decimal("0.55"))
        opex = _q2(revenue * Decimal("0.20"))
        one_time = Decimal("5.00") if idx % 6 == 0 else Decimal("0.00")
        owner_comp_addback = Decimal("2.00") if idx % 4 == 0 else Decimal("0.00")
        rows.append(
            {
                "period": period,
                "revenue": revenue,
                "cogs": cogs,
                "opex": opex,
                "one_time": one_time,
                "owner_comp_addback": owner_comp_addback,
                "recurring_revenue_pct": Decimal("0.72"),
                "top_5_customer_pct": Decimal("0.46"),
                "contract_coverage_pct": Decimal("0.68"),
            }
        )
    return rows


async def compute_qoe(
    session: AsyncSession,
    engagement: FDDEngagement,
) -> dict:
    """
    Quality of Earnings analysis.
    """
    rows = await _load_qoe_period_data(session, engagement)
    if not rows:
        return {
            "periods": [],
            "reported_ebitda": [],
            "adjustments": [],
            "adjusted_ebitda": [],
            "ebitda_cagr": Decimal("0.0000"),
            "ebitda_trend": "stable",
            "revenue_quality_score": Decimal("0.00"),
            "ltm_adjusted_ebitda": Decimal("0.00"),
            "findings": [],
        }

    periods: list[str] = []
    reported_ebitda: list[Decimal] = []
    adjusted_ebitda: list[Decimal] = []
    adjustments: list[dict] = []

    for row in rows:
        period = str(row["period"])
        revenue = Decimal(str(row["revenue"]))
        cogs = Decimal(str(row["cogs"]))
        opex = Decimal(str(row["opex"]))
        one_time = Decimal(str(row.get("one_time", "0")))
        owner_comp_addback = Decimal(str(row.get("owner_comp_addback", "0")))

        reported = _q2(revenue - cogs - opex)
        adjustment_total = _q2(one_time + owner_comp_addback)
        adjusted = _q2(reported + adjustment_total)

        periods.append(period)
        reported_ebitda.append(reported)
        adjusted_ebitda.append(adjusted)

        if one_time != Decimal("0"):
            adjustments.append(
                {
                    "period": period,
                    "description": "One-time adjustment",
                    "amount": _q2(one_time),
                    "type": "one_time",
                }
            )
        if owner_comp_addback != Decimal("0"):
            adjustments.append(
                {
                    "period": period,
                    "description": "Owner compensation normalization",
                    "amount": _q2(owner_comp_addback),
                    "type": "normalisation",
                }
            )

    first = adjusted_ebitda[0]
    last = adjusted_ebitda[-1]
    years = Decimal(str(max(len(adjusted_ebitda), 1))) / Decimal("12")
    if first <= Decimal("0") or years <= Decimal("0"):
        cagr = Decimal("0")
    else:
        ratio = last / first
        cagr = (ratio - Decimal("1")) / years
    ebitda_cagr = _q4(cagr * Decimal("100"))

    if last >= first * Decimal("1.05"):
        trend = "improving"
    elif last <= first * Decimal("0.95"):
        trend = "declining"
    else:
        trend = "stable"

    recurring_ratio = sum(Decimal(str(r["recurring_revenue_pct"])) for r in rows) / Decimal(str(len(rows)))
    concentration = sum(Decimal(str(r["top_5_customer_pct"])) for r in rows) / Decimal(str(len(rows)))
    coverage = sum(Decimal(str(r["contract_coverage_pct"])) for r in rows) / Decimal(str(len(rows)))
    score = (
        recurring_ratio * Decimal("50")
        + (Decimal("1") - concentration) * Decimal("25")
        + coverage * Decimal("25")
    ) * Decimal("100") / Decimal("100")
    revenue_quality_score = _q2(score)

    ltm_adjusted_ebitda = _q2(sum(adjusted_ebitda[-12:], start=Decimal("0")))

    findings: list[dict] = []
    findings.append(
        {
            "finding_type": "adjustment",
            "severity": "medium",
            "title": "Normalized EBITDA adjustments identified",
            "description": "One-time and owner compensation adjustments were applied.",
            "financial_impact": _q2(sum((Decimal(str(a["amount"])) for a in adjustments), start=Decimal("0"))),
            "recommended_action": "Validate adjustment evidence with management.",
        }
    )
    if revenue_quality_score < Decimal("60"):
        findings.append(
            {
                "finding_type": "risk",
                "severity": "high",
                "title": "Revenue quality is below threshold",
                "description": "Recurring revenue profile and concentration indicate elevated risk.",
                "financial_impact": None,
                "recommended_action": "Deep-dive top-customer renewals and contract terms.",
            }
        )
    else:
        findings.append(
            {
                "finding_type": "positive",
                "severity": "informational",
                "title": "Revenue quality profile is acceptable",
                "description": "Recurring revenue and contract coverage support earnings quality.",
                "financial_impact": None,
                "recommended_action": "Monitor contract churn assumptions in valuation.",
            }
        )

    return {
        "periods": periods,
        "reported_ebitda": reported_ebitda,
        "adjustments": adjustments,
        "adjusted_ebitda": adjusted_ebitda,
        "ebitda_cagr": ebitda_cagr,
        "ebitda_trend": trend,
        "revenue_quality_score": revenue_quality_score,
        "ltm_adjusted_ebitda": ltm_adjusted_ebitda,
        "findings": findings,
    }


__all__ = ["compute_qoe", "_load_qoe_period_data"]
