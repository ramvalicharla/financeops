from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.forecasting.models import ForecastAssumption
from financeops.modules.forecasting.service import _apply_growth_rate
from financeops.modules.scenario_modelling.models import (
    ScenarioDefinition,
    ScenarioLineItem,
    ScenarioResult,
    ScenarioSet,
)


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _as_decimal(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value))


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
    index = year * 12 + (month - 1) + delta_months
    out_year = index // 12
    out_month = (index % 12) + 1
    return f"{out_year:04d}-{out_month:02d}"


async def _load_scenario_set(session: AsyncSession, *, tenant_id: uuid.UUID, scenario_set_id: uuid.UUID) -> ScenarioSet:
    row = (
        await session.execute(
            select(ScenarioSet).where(
                ScenarioSet.id == scenario_set_id,
                ScenarioSet.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Scenario set not found")
    return row


async def _load_definition(session: AsyncSession, *, tenant_id: uuid.UUID, definition_id: uuid.UUID) -> ScenarioDefinition:
    row = (
        await session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.id == definition_id,
                ScenarioDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Scenario definition not found")
    return row


async def _base_assumptions(session: AsyncSession, scenario_set: ScenarioSet) -> dict[str, Decimal]:
    defaults = {
        "revenue_growth_pct_monthly": Decimal("5.00"),
        "cogs_pct_of_revenue": Decimal("60.00"),
        "opex_growth_pct_monthly": Decimal("3.00"),
    }
    if scenario_set.base_forecast_run_id is None:
        return defaults

    rows = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.tenant_id == scenario_set.tenant_id,
                ForecastAssumption.forecast_run_id == scenario_set.base_forecast_run_id,
            )
        )
    ).scalars().all()
    if not rows:
        return defaults

    values = dict(defaults)
    for row in rows:
        values[row.assumption_key] = _as_decimal(row.assumption_value)
    return values


async def create_scenario_set(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    base_period: str,
    horizon_months: int,
    created_by: uuid.UUID,
    base_forecast_run_id: uuid.UUID | None = None,
) -> ScenarioSet:
    """
    Create a scenario set with base/optimistic/pessimistic defaults.
    """
    _period_parts(base_period)
    scenario_set = ScenarioSet(
        tenant_id=tenant_id,
        name=name,
        base_period=base_period,
        horizon_months=horizon_months,
        created_by=created_by,
        base_forecast_run_id=base_forecast_run_id,
    )
    session.add(scenario_set)
    await session.flush()

    defaults = [
        {
            "scenario_name": "base",
            "scenario_label": "Base Case",
            "is_base_case": True,
            "driver_overrides": {},
            "colour_hex": "#378ADD",
        },
        {
            "scenario_name": "optimistic",
            "scenario_label": "Optimistic Case",
            "is_base_case": False,
            "driver_overrides": {
                "revenue_growth_pct_monthly": "8.00",
                "cogs_pct_of_revenue": "55.00",
            },
            "colour_hex": "#16A34A",
        },
        {
            "scenario_name": "pessimistic",
            "scenario_label": "Pessimistic Case",
            "is_base_case": False,
            "driver_overrides": {
                "revenue_growth_pct_monthly": "2.00",
                "cogs_pct_of_revenue": "68.00",
            },
            "colour_hex": "#DC2626",
        },
    ]
    for item in defaults:
        session.add(
            ScenarioDefinition(
                scenario_set_id=scenario_set.id,
                tenant_id=tenant_id,
                scenario_name=item["scenario_name"],
                scenario_label=item["scenario_label"],
                is_base_case=item["is_base_case"],
                driver_overrides=item["driver_overrides"],
                colour_hex=item["colour_hex"],
            )
        )
    await session.flush()
    return scenario_set


async def update_scenario_drivers(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    scenario_definition_id: uuid.UUID,
    driver_overrides: dict[str, str],
) -> ScenarioDefinition:
    """
    Update driver overrides after validating Decimal-string values.
    """
    definition = await _load_definition(
        session,
        tenant_id=tenant_id,
        definition_id=scenario_definition_id,
    )
    validated: dict[str, str] = {}
    for key, value in driver_overrides.items():
        try:
            Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid decimal value for {key}") from exc
        validated[str(key)] = str(value)
    definition.driver_overrides = validated
    definition.updated_at = datetime.now(UTC)
    await session.flush()
    return definition


async def compute_scenario(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    scenario_definition_id: uuid.UUID,
) -> ScenarioResult:
    """
    Compute one scenario and persist append-only result + line items.
    """
    definition = await _load_definition(
        session,
        tenant_id=tenant_id,
        definition_id=scenario_definition_id,
    )
    scenario_set = await _load_scenario_set(
        session,
        tenant_id=tenant_id,
        scenario_set_id=definition.scenario_set_id,
    )
    assumptions = await _base_assumptions(session, scenario_set)
    for key, value in (definition.driver_overrides or {}).items():
        assumptions[key] = _as_decimal(value)

    revenue_growth = assumptions.get("revenue_growth_pct_monthly", Decimal("5.00"))
    cogs_pct = assumptions.get("cogs_pct_of_revenue", Decimal("60.00"))
    opex_growth = assumptions.get("opex_growth_pct_monthly", Decimal("3.00"))

    result = ScenarioResult(
        scenario_set_id=scenario_set.id,
        scenario_definition_id=definition.id,
        tenant_id=tenant_id,
    )
    session.add(result)
    await session.flush()

    prior_revenue = Decimal("1000000.00")
    prior_opex = Decimal("250000.00")
    for month in range(1, scenario_set.horizon_months + 1):
        period = _shift_period(scenario_set.base_period, month)
        revenue = _q2(_apply_growth_rate(prior_revenue, revenue_growth))
        cogs = _q2(revenue * cogs_pct / Decimal("100"))
        gross_profit = _q2(revenue - cogs)
        opex = _q2(_apply_growth_rate(prior_opex, opex_growth))
        ebitda = _q2(gross_profit - opex)
        net_profit = _q2(ebitda * Decimal("0.80"))

        for line_item, category, amount in (
            ("Revenue", "Revenue", revenue),
            ("COGS", "Cost of Revenue", cogs),
            ("Gross Profit", "Gross Profit", gross_profit),
            ("Operating Expenses", "Operating Expenses", opex),
            ("EBITDA", "EBITDA", ebitda),
            ("Net Profit", "Net Profit", net_profit),
        ):
            session.add(
                ScenarioLineItem(
                    scenario_result_id=result.id,
                    scenario_set_id=scenario_set.id,
                    tenant_id=tenant_id,
                    period=period,
                    mis_line_item=line_item,
                    mis_category=category,
                    amount=amount,
                )
            )
        prior_revenue = revenue
        prior_opex = opex
    await session.flush()
    return result


async def compute_all_scenarios(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    scenario_set_id: uuid.UUID,
) -> list[ScenarioResult]:
    """
    Compute all scenarios in a set.
    """
    definitions = (
        await session.execute(
            select(ScenarioDefinition)
            .where(
                ScenarioDefinition.tenant_id == tenant_id,
                ScenarioDefinition.scenario_set_id == scenario_set_id,
            )
            .order_by(ScenarioDefinition.created_at.asc(), ScenarioDefinition.id.asc())
        )
    ).scalars().all()
    results: list[ScenarioResult] = []
    for definition in definitions:
        results.append(await compute_scenario(session, tenant_id, definition.id))
    return results


async def get_scenario_comparison(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    scenario_set_id: uuid.UUID,
) -> dict:
    """
    Return side-by-side comparison for latest result of each scenario.
    """
    scenario_set = await _load_scenario_set(
        session,
        tenant_id=tenant_id,
        scenario_set_id=scenario_set_id,
    )
    definitions = (
        await session.execute(
            select(ScenarioDefinition)
            .where(
                ScenarioDefinition.tenant_id == tenant_id,
                ScenarioDefinition.scenario_set_id == scenario_set_id,
            )
            .order_by(ScenarioDefinition.created_at.asc(), ScenarioDefinition.id.asc())
        )
    ).scalars().all()

    scenarios_payload: list[dict] = []
    base_ebitda = Decimal("0")
    optimistic_ebitda = Decimal("0")
    pessimistic_ebitda = Decimal("0")

    for definition in definitions:
        latest_result = (
            await session.execute(
                select(ScenarioResult)
                .where(
                    ScenarioResult.tenant_id == tenant_id,
                    ScenarioResult.scenario_definition_id == definition.id,
                )
                .order_by(desc(ScenarioResult.computed_at), desc(ScenarioResult.id))
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_result is None:
            continue
        line_items = (
            await session.execute(
                select(ScenarioLineItem).where(
                    ScenarioLineItem.tenant_id == tenant_id,
                    ScenarioLineItem.scenario_result_id == latest_result.id,
                )
            )
        ).scalars().all()

        revenue_total = _q2(sum((_as_decimal(row.amount) for row in line_items if row.mis_line_item == "Revenue"), start=Decimal("0")))
        ebitda_total = _q2(sum((_as_decimal(row.amount) for row in line_items if row.mis_line_item == "EBITDA"), start=Decimal("0")))
        net_profit_total = _q2(sum((_as_decimal(row.amount) for row in line_items if row.mis_line_item == "Net Profit"), start=Decimal("0")))
        ebitda_margin_pct = Decimal("0")
        if revenue_total != Decimal("0"):
            ebitda_margin_pct = _q4((ebitda_total / revenue_total) * Decimal("100"))

        periods = sorted({row.period for row in line_items})
        monthly: list[dict] = []
        for period in periods:
            period_revenue = _q2(sum((_as_decimal(row.amount) for row in line_items if row.period == period and row.mis_line_item == "Revenue"), start=Decimal("0")))
            period_ebitda = _q2(sum((_as_decimal(row.amount) for row in line_items if row.period == period and row.mis_line_item == "EBITDA"), start=Decimal("0")))
            monthly.append({"period": period, "revenue": period_revenue, "ebitda": period_ebitda})

        if definition.is_base_case:
            base_ebitda = ebitda_total
        if definition.scenario_name == "optimistic":
            optimistic_ebitda = ebitda_total
        if definition.scenario_name == "pessimistic":
            pessimistic_ebitda = ebitda_total

        scenarios_payload.append(
            {
                "scenario_name": definition.scenario_name,
                "scenario_label": definition.scenario_label,
                "colour_hex": definition.colour_hex,
                "is_base_case": definition.is_base_case,
                "summary": {
                    "revenue_total": revenue_total,
                    "ebitda_total": ebitda_total,
                    "ebitda_margin_pct": ebitda_margin_pct,
                    "net_profit_total": net_profit_total,
                },
                "monthly": monthly,
            }
        )

    if optimistic_ebitda == Decimal("0"):
        optimistic_ebitda = base_ebitda
    if pessimistic_ebitda == Decimal("0"):
        pessimistic_ebitda = base_ebitda

    optimistic_delta = _q2(optimistic_ebitda - base_ebitda)
    driver_one = _q2(optimistic_delta * Decimal("0.60"))
    driver_two = _q2(optimistic_delta - driver_one)

    return {
        "scenario_set_name": scenario_set.name,
        "base_period": scenario_set.base_period,
        "scenarios": scenarios_payload,
        "waterfall": {
            "base_ebitda": base_ebitda,
            "drivers": [
                {"driver_name": "revenue_growth_pct_monthly", "impact": driver_one},
                {"driver_name": "cogs_pct_of_revenue", "impact": driver_two},
            ],
            "optimistic_ebitda": optimistic_ebitda,
            "pessimistic_ebitda": pessimistic_ebitda,
        },
    }


__all__ = [
    "create_scenario_set",
    "update_scenario_drivers",
    "compute_scenario",
    "compute_all_scenarios",
    "get_scenario_comparison",
]

