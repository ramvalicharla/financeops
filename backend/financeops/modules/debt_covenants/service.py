from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.users import IamUser, UserRole
from financeops.modules.budgeting.models import BudgetLineItem
from financeops.modules.cash_flow_forecast.models import CashFlowForecastAssumption
from financeops.modules.debt_covenants.models import CovenantBreachEvent, CovenantDefinition
from financeops.modules.notifications.service import send_notification

_RATIO = Decimal("0.000001")
_PCT = Decimal("0.0001")


def _decimal(value: Decimal | int | str | None, quant: Decimal = _RATIO) -> Decimal:
    if value is None:
        return Decimal("0").quantize(quant)
    return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0.000000")
    return (numerator / denominator).quantize(_RATIO, rounding=ROUND_HALF_UP)


async def _financial_snapshot(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Decimal]:
    annual = (
        await session.execute(
            select(func.coalesce(func.sum(BudgetLineItem.annual_total), 0)).where(BudgetLineItem.tenant_id == tenant_id)
        )
    ).scalar_one()
    annual_total = Decimal(str(annual)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    debt = (annual_total.copy_abs() * Decimal("0.40")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    equity = (annual_total.copy_abs() * Decimal("0.60")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ebitda = (annual_total * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ebit = (annual_total * Decimal("0.16")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    interest = (debt * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    current_assets = (annual_total * Decimal("0.35")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    current_liabilities = (annual_total * Decimal("0.25")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    taxes = (annual_total * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    capex = (annual_total * Decimal("0.06")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    debt_service = (debt * Decimal("0.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    latest_cash = (
        await session.execute(
            select(CashFlowForecastAssumption.closing_balance)
            .where(CashFlowForecastAssumption.tenant_id == tenant_id)
            .order_by(desc(CashFlowForecastAssumption.updated_at), desc(CashFlowForecastAssumption.id))
            .limit(1)
        )
    ).scalar_one_or_none()
    cash = Decimal(str(latest_cash or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "total_debt": debt,
        "ltm_ebitda": ebitda,
        "ebit": ebit,
        "interest_expense": interest,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "total_equity": equity,
        "cash": cash,
        "taxes": taxes,
        "capex": capex,
        "debt_service": debt_service,
        "net_debt": (debt - cash).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


async def compute_covenant_value(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    covenant_type: str,
    period: str,
) -> Decimal:
    del period
    snap = await _financial_snapshot(session, tenant_id)

    if covenant_type == "debt_to_ebitda":
        return _safe_div(snap["total_debt"], snap["ltm_ebitda"])
    if covenant_type == "interest_coverage":
        return _safe_div(snap["ebit"], snap["interest_expense"])
    if covenant_type == "current_ratio":
        return _safe_div(snap["current_assets"], snap["current_liabilities"])
    if covenant_type == "debt_to_equity":
        return _safe_div(snap["total_debt"], snap["total_equity"])
    if covenant_type == "minimum_cash_balance":
        return _decimal(snap["cash"], _RATIO)
    if covenant_type == "dscr":
        numerator = (snap["ltm_ebitda"] - snap["taxes"] - snap["capex"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return _safe_div(numerator, snap["debt_service"])
    if covenant_type == "leverage_ratio":
        return _safe_div(snap["net_debt"], snap["ltm_ebitda"])
    if covenant_type == "net_worth":
        return _decimal(snap["total_equity"], _RATIO)
    return Decimal("0.000000")


def _variance_pct(actual: Decimal, threshold: Decimal) -> Decimal:
    if threshold == Decimal("0"):
        return Decimal("0.0000")
    return (((actual - threshold) / threshold.copy_abs()) * Decimal("100")).quantize(_PCT, rounding=ROUND_HALF_UP)


def _classify_breach(actual: Decimal, threshold: Decimal, direction: str, notification_threshold_pct: Decimal) -> str:
    threshold = _decimal(threshold)
    actual = _decimal(actual)
    notify_ratio = (Decimal(str(notification_threshold_pct)) / Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if direction == "below":
        if actual > threshold:
            return "breach"
        near_threshold = (threshold * notify_ratio).quantize(_RATIO, rounding=ROUND_HALF_UP)
        if actual >= near_threshold:
            return "near_breach"
        return "pass"

    if actual < threshold:
        return "breach"
    upper_band = (threshold / notify_ratio).quantize(_RATIO, rounding=ROUND_HALF_UP) if notify_ratio > Decimal("0") else threshold
    if actual <= upper_band:
        return "near_breach"
    return "pass"


async def _notify_if_needed(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    event: CovenantBreachEvent,
    definition: CovenantDefinition,
) -> None:
    if event.breach_type not in {"breach", "near_breach"}:
        return
    finance_leader = (
        await session.execute(
            select(IamUser)
            .where(
                IamUser.tenant_id == tenant_id,
                IamUser.role == UserRole.finance_leader,
                IamUser.is_active.is_(True),
            )
            .order_by(IamUser.created_at)
        )
    ).scalars().first()
    if finance_leader is None:
        return
    await send_notification(
        session,
        tenant_id=tenant_id,
        recipient_user_id=finance_leader.id,
        notification_type="system_alert",
        title=f"Covenant {event.breach_type.replace('_', ' ')}: {definition.covenant_label}",
        body=(
            f"{definition.facility_name} {definition.covenant_type} actual={event.actual_value} "
            f"threshold={event.threshold_value} period={event.period}"
        ),
        action_url="/covenants",
        metadata={"covenant_id": str(definition.id), "event_id": str(event.id), "period": event.period},
    )


async def check_all_covenants(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
) -> list[CovenantBreachEvent]:
    # unbounded-ok: active covenant definitions are tenant-scoped and operationally capped.
    # Full active set is required to compute period compliance in one run.
    defs = (
        await session.execute(
            select(CovenantDefinition)
            .where(CovenantDefinition.tenant_id == tenant_id, CovenantDefinition.is_active.is_(True))
            .order_by(CovenantDefinition.created_at)
        )
    ).scalars().all()

    events: list[CovenantBreachEvent] = []
    for definition in defs:
        actual = await compute_covenant_value(session, tenant_id, definition.covenant_type, period)
        threshold = _decimal(definition.threshold_value)
        breach_type = _classify_breach(actual, threshold, definition.threshold_direction, Decimal(str(definition.notification_threshold_pct)))

        event = CovenantBreachEvent(
            covenant_id=definition.id,
            tenant_id=tenant_id,
            period=period,
            actual_value=actual,
            threshold_value=threshold,
            breach_type=breach_type,
            variance_pct=_variance_pct(actual, threshold),
        )
        session.add(event)
        await session.flush()
        await _notify_if_needed(session, tenant_id, event, definition)
        events.append(event)

    return events


async def get_all_covenants(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[CovenantDefinition]:
    result = await session.execute(
        select(CovenantDefinition)
        .where(CovenantDefinition.tenant_id == tenant_id)
        .where(CovenantDefinition.is_active.is_(True))
        .order_by(desc(CovenantDefinition.created_at), desc(CovenantDefinition.id))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


def _headroom_pct(definition: CovenantDefinition, event: CovenantBreachEvent | None) -> Decimal:
    if event is None:
        return Decimal("0.0000")
    threshold = Decimal(str(definition.threshold_value))
    if threshold == Decimal("0"):
        return Decimal("0.0000")
    actual = Decimal(str(event.actual_value))

    if definition.threshold_direction == "below":
        value = ((threshold - actual) / threshold.copy_abs()) * Decimal("100")
    else:
        value = ((actual - threshold) / threshold.copy_abs()) * Decimal("100")
    return value.quantize(_PCT, rounding=ROUND_HALF_UP)


def _trend(latest: CovenantBreachEvent | None, previous: CovenantBreachEvent | None) -> str:
    if latest is None or previous is None:
        return "stable"
    if latest.variance_pct > previous.variance_pct:
        return "worsening"
    if latest.variance_pct < previous.variance_pct:
        return "improving"
    return "stable"


async def get_covenant_dashboard(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    defs = await get_all_covenants(session, tenant_id=tenant_id, limit=100, offset=0)

    rows: list[dict] = []
    passing = 0
    near = 0
    breached = 0

    for definition in defs:
        latest_two = (
            await session.execute(
                select(CovenantBreachEvent)
                .where(CovenantBreachEvent.covenant_id == definition.id)
                .order_by(desc(CovenantBreachEvent.computed_at), desc(CovenantBreachEvent.id))
                .limit(2)
            )
        ).scalars().all()
        latest = latest_two[0] if latest_two else None
        previous = latest_two[1] if len(latest_two) > 1 else None

        if latest is not None:
            if latest.breach_type == "pass":
                passing += 1
            elif latest.breach_type == "near_breach":
                near += 1
            else:
                breached += 1

        rows.append(
            {
                "definition": definition,
                "latest_event": latest,
                "trend": _trend(latest, previous),
                "headroom_pct": _headroom_pct(definition, latest),
            }
        )

    return {
        "total_covenants": len(defs),
        "passing": passing,
        "near_breach": near,
        "breached": breached,
        "covenants": rows,
    }


__all__ = [
    "compute_covenant_value",
    "check_all_covenants",
    "get_all_covenants",
    "get_covenant_dashboard",
]
