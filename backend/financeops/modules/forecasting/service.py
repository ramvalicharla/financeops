from __future__ import annotations

import calendar
import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.modules.forecasting.models import ForecastAssumption, ForecastLineItem, ForecastRun


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _period_parts(period: str) -> tuple[int, int]:
    try:
        year_text, month_text = str(period).split("-", 1)
        year = int(year_text)
        month = int(month_text)
    except (TypeError, ValueError) as exc:
        raise ValidationError("period must be in YYYY-MM format") from exc
    if month < 1 or month > 12:
        raise ValidationError("period month must be between 01 and 12")
    return year, month


def _shift_period(period: str, delta_months: int) -> str:
    year, month = _period_parts(period)
    index = (year * 12 + (month - 1)) + delta_months
    target_year = index // 12
    target_month = (index % 12) + 1
    return f"{target_year:04d}-{target_month:02d}"


def _as_decimal(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value))


def _round_money(value: Decimal) -> Decimal:
    return _as_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_rate(value: Decimal) -> Decimal:
    return _as_decimal(value).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _apply_growth_rate(base: Decimal, rate_pct: Decimal) -> Decimal:
    growth_multiplier = Decimal("1") + (_as_decimal(rate_pct) / Decimal("100"))
    return _round_money(_as_decimal(base) * growth_multiplier)


async def _load_run(session: AsyncSession, *, tenant_id: uuid.UUID, forecast_run_id: uuid.UUID) -> ForecastRun:
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == forecast_run_id,
                ForecastRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Forecast run not found")
    return run


async def _assumption_map(session: AsyncSession, run: ForecastRun) -> dict[str, Decimal]:
    rows = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.tenant_id == run.tenant_id,
                ForecastAssumption.forecast_run_id == run.id,
            )
        )
    ).scalars().all()
    return {row.assumption_key: _as_decimal(row.assumption_value) for row in rows}


async def _seed_default_assumptions(session: AsyncSession, run: ForecastRun) -> list[ForecastAssumption]:
    defaults = [
        (
            "revenue_growth_pct_monthly",
            Decimal("5.000000"),
            "Revenue growth % monthly",
            "growth",
        ),
        (
            "cogs_pct_of_revenue",
            Decimal("60.000000"),
            "COGS % of Revenue",
            "margins",
        ),
        (
            "opex_growth_pct_monthly",
            Decimal("3.000000"),
            "Operating expense growth % monthly",
            "growth",
        ),
    ]
    rows: list[ForecastAssumption] = []
    for key, value, label, category in defaults:
        row = ForecastAssumption(
            forecast_run_id=run.id,
            tenant_id=run.tenant_id,
            assumption_key=key,
            assumption_value=value,
            assumption_label=label,
            category=category,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def create_forecast_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    run_name: str,
    forecast_type: str,
    base_period: str,
    horizon_months: int,
    created_by: uuid.UUID,
) -> ForecastRun:
    """
    Create a new forecast run and seed default assumptions.
    """
    _period_parts(base_period)
    if horizon_months not in {3, 6, 12, 24}:
        raise ValidationError("horizon_months must be one of: 3, 6, 12, 24")
    run = ForecastRun(
        tenant_id=tenant_id,
        run_name=run_name,
        forecast_type=forecast_type,
        base_period=base_period,
        horizon_months=horizon_months,
        status="draft",
        created_by=created_by,
    )
    session.add(run)
    await session.flush()
    await _seed_default_assumptions(session, run)
    return run


async def update_assumption(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
    assumption_key: str,
    new_value: Decimal,
    basis: str | None = None,
) -> ForecastAssumption:
    """
    Update a single assumption and recompute forecast lines.
    """
    row = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.tenant_id == tenant_id,
                ForecastAssumption.forecast_run_id == forecast_run_id,
                ForecastAssumption.assumption_key == assumption_key,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Forecast assumption not found")
    row.assumption_value = _as_decimal(new_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    row.basis = basis
    row.updated_at = datetime.now(UTC)
    await session.flush()
    await compute_forecast_lines(
        session,
        tenant_id=tenant_id,
        forecast_run_id=forecast_run_id,
    )
    return row


async def compute_forecast_lines(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
) -> list[ForecastLineItem]:
    """
    Compute forecast line items from assumptions using Decimal arithmetic.
    """
    run = await _load_run(session, tenant_id=tenant_id, forecast_run_id=forecast_run_id)
    assumptions = await _assumption_map(session, run)

    revenue_growth = assumptions.get("revenue_growth_pct_monthly", Decimal("5.0"))
    cogs_pct = assumptions.get("cogs_pct_of_revenue", Decimal("60.0"))
    opex_growth = assumptions.get("opex_growth_pct_monthly", Decimal("3.0"))

    base_revenue = Decimal("1000000.00")
    base_opex = Decimal("250000.00")

    created_rows: list[ForecastLineItem] = []

    # Historical context: last 6 months as actuals.
    for offset in range(-6, 0):
        period = _shift_period(run.base_period, offset)
        months_ago = abs(offset)
        historical_revenue = _round_money(base_revenue * (Decimal("1") - Decimal("0.02") * Decimal(str(months_ago))))
        historical_cogs = _round_money(historical_revenue * cogs_pct / Decimal("100"))
        historical_opex = _round_money(base_opex * (Decimal("1") - Decimal("0.01") * Decimal(str(months_ago))))
        historical_ebitda = _round_money(historical_revenue - historical_cogs - historical_opex)
        for line_item, category, amount in (
            ("Revenue", "Revenue", historical_revenue),
            ("COGS", "Cost of Revenue", historical_cogs),
            ("Operating Expenses", "Operating Expenses", historical_opex),
            ("EBITDA", "EBITDA", historical_ebitda),
        ):
            row = ForecastLineItem(
                forecast_run_id=run.id,
                tenant_id=tenant_id,
                period=period,
                is_actual=True,
                mis_line_item=line_item,
                mis_category=category,
                amount=amount,
            )
            session.add(row)
            created_rows.append(row)

    prior_revenue = base_revenue
    prior_opex = base_opex
    for step in range(1, run.horizon_months + 1):
        period = _shift_period(run.base_period, step)
        forecast_revenue = _apply_growth_rate(prior_revenue, revenue_growth)
        forecast_cogs = _round_money(forecast_revenue * cogs_pct / Decimal("100"))
        forecast_gp = _round_money(forecast_revenue - forecast_cogs)
        forecast_opex = _apply_growth_rate(prior_opex, opex_growth)
        forecast_ebitda = _round_money(forecast_gp - forecast_opex)

        for line_item, category, amount in (
            ("Revenue", "Revenue", forecast_revenue),
            ("COGS", "Cost of Revenue", forecast_cogs),
            ("Gross Profit", "Gross Profit", forecast_gp),
            ("Operating Expenses", "Operating Expenses", forecast_opex),
            ("EBITDA", "EBITDA", forecast_ebitda),
        ):
            row = ForecastLineItem(
                forecast_run_id=run.id,
                tenant_id=tenant_id,
                period=period,
                is_actual=False,
                mis_line_item=line_item,
                mis_category=category,
                amount=amount,
            )
            session.add(row)
            created_rows.append(row)

        prior_revenue = forecast_revenue
        prior_opex = forecast_opex

    await session.flush()
    return created_rows


async def publish_forecast(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
    published_by: uuid.UUID,
) -> ForecastRun:
    """
    Publish a forecast run and supersede previously published run.
    """
    run = await _load_run(session, tenant_id=tenant_id, forecast_run_id=forecast_run_id)
    now = datetime.now(UTC)
    await session.execute(
        update(ForecastRun)
        .where(
            ForecastRun.tenant_id == tenant_id,
            ForecastRun.id != run.id,
            ForecastRun.is_published.is_(True),
        )
        .values(is_published=False, status="superseded")
    )
    run.is_published = True
    run.published_at = now
    run.published_by = published_by
    run.status = "published"
    await session.flush()
    return run


async def get_forecast_vs_budget(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
    fiscal_year: int,
) -> dict:
    """
    Compare published forecast to approved budget.
    """
    run = await _load_run(session, tenant_id=tenant_id, forecast_run_id=forecast_run_id)
    budget_version = (
        await session.execute(
            select(BudgetVersion).where(
                BudgetVersion.tenant_id == tenant_id,
                BudgetVersion.fiscal_year == fiscal_year,
                BudgetVersion.status == "approved",
            )
            .order_by(desc(BudgetVersion.version_number))
            .limit(1)
        )
    ).scalar_one_or_none()
    if budget_version is None:
        raise NotFoundError("No approved budget version for fiscal year")

    budget_lines = (
        await session.execute(
            select(BudgetLineItem).where(
                BudgetLineItem.tenant_id == tenant_id,
                BudgetLineItem.budget_version_id == budget_version.id,
            )
        )
    ).scalars().all()
    budget_map: dict[tuple[str, int], Decimal] = {}
    for line in budget_lines:
        for month in range(1, 13):
            budget_map[(line.mis_line_item, month)] = _q2(_as_decimal(getattr(line, f"month_{month:02d}")))

    all_forecast_rows = (
        await session.execute(
            select(ForecastLineItem)
            .where(
                ForecastLineItem.tenant_id == tenant_id,
                ForecastLineItem.forecast_run_id == run.id,
                ForecastLineItem.is_actual.is_(False),
            )
            .order_by(
                ForecastLineItem.period.asc(),
                ForecastLineItem.mis_line_item.asc(),
                ForecastLineItem.created_at.desc(),
                ForecastLineItem.id.desc(),
            )
        )
    ).scalars().all()

    latest_rows: dict[tuple[str, str], ForecastLineItem] = {}
    for row in all_forecast_rows:
        key = (row.period, row.mis_line_item)
        if key not in latest_rows:
            latest_rows[key] = row

    rows: list[dict] = []
    for key in sorted(latest_rows):
        row = latest_rows[key]
        _, month = _period_parts(row.period)
        budget_amount = _q2(budget_map.get((row.mis_line_item, month), Decimal("0")))
        forecast_amount = _q2(_as_decimal(row.amount))
        variance = _q2(forecast_amount - budget_amount)
        variance_pct = Decimal("0")
        if budget_amount != Decimal("0"):
            variance_pct = _round_rate((variance / budget_amount) * Decimal("100"))
        rows.append(
            {
                "period": row.period,
                "mis_line_item": row.mis_line_item,
                "budget": budget_amount,
                "forecast": forecast_amount,
                "variance": variance,
                "variance_pct": variance_pct,
            }
        )

    return {
        "forecast_run_id": str(run.id),
        "fiscal_year": fiscal_year,
        "rows": rows,
    }


__all__ = [
    "_apply_growth_rate",
    "create_forecast_run",
    "update_assumption",
    "compute_forecast_lines",
    "publish_forecast",
    "get_forecast_vs_budget",
]

