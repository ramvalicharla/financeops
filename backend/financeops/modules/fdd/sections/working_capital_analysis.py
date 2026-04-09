from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
from financeops.modules.fdd.models import FDDEngagement
from financeops.modules.working_capital.models import WCSnapshot


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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


def _system_actor(engagement: FDDEngagement, *, period: str) -> IntentActor:
    return IntentActor(
        user_id=engagement.created_by,
        tenant_id=engagement.tenant_id,
        role="finance_leader",
        source_channel=IntentSourceChannel.SYSTEM.value,
        correlation_id=f"fdd-working-capital:{engagement.id}:{period}",
    )


def _idempotency_key(engagement: FDDEngagement, *, period: str) -> str:
    raw = json.dumps(
        {
            "tenant_id": str(engagement.tenant_id),
            "engagement_id": str(engagement.id),
            "period": period,
            "intent_type": IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT.value,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def compute_wc_analysis(
    session: AsyncSession,
    engagement: FDDEngagement,
) -> dict:
    periods = _iter_periods(engagement.analysis_period_start, engagement.analysis_period_end)
    periods = periods[-12:]

    nwc_values: list[Decimal] = []
    dso_values: list[Decimal] = []
    dpo_values: list[Decimal] = []

    for period in periods:
        snapshot = (
            await session.execute(
                select(WCSnapshot).where(
                    WCSnapshot.tenant_id == engagement.tenant_id,
                    WCSnapshot.period == period,
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            result = await IntentService(session).submit_intent(
                intent_type=IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT,
                actor=_system_actor(engagement, period=period),
                payload={"period": period},
                idempotency_key=_idempotency_key(engagement, period=period),
            )
            snapshot = (
                await session.execute(
                    select(WCSnapshot).where(
                        WCSnapshot.id == result.record_refs["snapshot_id"],
                        WCSnapshot.tenant_id == engagement.tenant_id,
                    )
                )
            ).scalar_one()
        nwc_values.append(Decimal(str(snapshot.net_working_capital)))
        dso_values.append(Decimal(str(snapshot.dso_days)))
        dpo_values.append(Decimal(str(snapshot.dpo_days)))

    if not nwc_values:
        return {
            "periods": [],
            "nwc_by_period": [],
            "average_nwc": Decimal("0.00"),
            "nwc_peg": Decimal("0.00"),
            "nwc_seasonality_range": Decimal("0.00"),
            "dso_trend": [],
            "dpo_trend": [],
            "outlier_periods": [],
            "adjustment_recommendation": Decimal("0.00"),
            "findings": [],
        }

    average_nwc = _q2(sum(nwc_values, start=Decimal("0")) / Decimal(str(len(nwc_values))))
    max_nwc = max(nwc_values)
    min_nwc = min(nwc_values)
    seasonality = _q2(max_nwc - min_nwc)
    nwc_peg = average_nwc
    latest_nwc = nwc_values[-1]
    adjustment_recommendation = _q2(average_nwc - latest_nwc)

    upper = average_nwc * Decimal("1.25")
    lower = average_nwc * Decimal("0.75")
    outlier_periods = [
        period
        for period, value in zip(periods, nwc_values)
        if value > upper or value < lower
    ]

    findings = [
        {
            "finding_type": "adjustment",
            "severity": "medium",
            "title": "Normalized working capital peg estimated",
            "description": "Average normalised NWC computed from trailing periods.",
            "financial_impact": adjustment_recommendation,
            "recommended_action": "Use peg in SPA completion accounts mechanism.",
        }
    ]
    if seasonality > Decimal("500000"):
        findings.append(
            {
                "finding_type": "risk",
                "severity": "high",
                "title": "Working capital seasonality is material",
                "description": "NWC seasonality band indicates closing-date sensitivity.",
                "financial_impact": seasonality,
                "recommended_action": "Set collar / averaging mechanism around peg.",
            }
        )

    return {
        "periods": periods,
        "nwc_by_period": [_q2(v) for v in nwc_values],
        "average_nwc": average_nwc,
        "nwc_peg": nwc_peg,
        "nwc_seasonality_range": seasonality,
        "dso_trend": [_q2(v) for v in dso_values],
        "dpo_trend": [_q2(v) for v in dpo_values],
        "outlier_periods": outlier_periods,
        "adjustment_recommendation": adjustment_recommendation,
        "findings": findings,
    }


__all__ = ["compute_wc_analysis"]
