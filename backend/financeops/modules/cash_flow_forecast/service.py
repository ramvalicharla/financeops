from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.cash_flow_forecast.models import CashFlowForecastAssumption, CashFlowForecastRun
from financeops.modules.expense_management.models import ExpenseClaim

_MONEY_QUANT = Decimal("0.01")
_WEEKLY_DIVISOR = Decimal("4.33")


def _d(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def _is_monday(value: date) -> bool:
    return value.weekday() == 0


async def _get_run(session: AsyncSession, tenant_id: uuid.UUID, forecast_run_id: uuid.UUID) -> CashFlowForecastRun:
    run = (
        await session.execute(
            select(CashFlowForecastRun).where(
                CashFlowForecastRun.id == forecast_run_id,
                CashFlowForecastRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Forecast run not found")
    return run


async def _recompute_weeks(session: AsyncSession, run: CashFlowForecastRun) -> list[CashFlowForecastAssumption]:
    rows = (
        await session.execute(
            select(CashFlowForecastAssumption)
            .where(CashFlowForecastAssumption.forecast_run_id == run.id)
            .order_by(CashFlowForecastAssumption.week_number)
        )
    ).scalars().all()

    prior_close = _d(run.opening_cash_balance)
    now = datetime.now(UTC)
    for row in rows:
        row.total_inflows = _d(row.customer_collections) + _d(row.other_inflows)
        row.total_outflows = (
            _d(row.supplier_payments)
            + _d(row.payroll)
            + _d(row.rent_and_utilities)
            + _d(row.loan_repayments)
            + _d(row.tax_payments)
            + _d(row.capex)
            + _d(row.other_outflows)
        )
        row.net_cash_flow = (row.total_inflows - row.total_outflows).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        row.closing_balance = (prior_close + row.net_cash_flow).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
        row.updated_at = now
        prior_close = _d(row.closing_balance)

    await session.flush()
    return rows


async def create_forecast_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    run_name: str,
    base_date: date,
    opening_cash_balance: Decimal,
    currency: str,
    created_by: uuid.UUID,
    weeks: int = 13,
) -> CashFlowForecastRun:
    if not _is_monday(base_date):
        raise ValidationError("base_date must be a Monday")
    if weeks <= 0:
        raise ValidationError("weeks must be positive")

    run = CashFlowForecastRun(
        tenant_id=tenant_id,
        run_name=run_name,
        base_date=base_date,
        weeks=weeks,
        opening_cash_balance=_d(opening_cash_balance),
        currency=currency or "INR",
        status="draft",
        is_published=False,
        created_by=created_by,
    )
    session.add(run)
    await session.flush()

    for week_number in range(1, weeks + 1):
        start_date = base_date + timedelta(days=(week_number - 1) * 7)
        session.add(
            CashFlowForecastAssumption(
                forecast_run_id=run.id,
                tenant_id=tenant_id,
                week_number=week_number,
                week_start_date=start_date,
                customer_collections=Decimal("0.00"),
                other_inflows=Decimal("0.00"),
                supplier_payments=Decimal("0.00"),
                payroll=Decimal("0.00"),
                rent_and_utilities=Decimal("0.00"),
                loan_repayments=Decimal("0.00"),
                tax_payments=Decimal("0.00"),
                capex=Decimal("0.00"),
                other_outflows=Decimal("0.00"),
                total_inflows=Decimal("0.00"),
                total_outflows=Decimal("0.00"),
                net_cash_flow=Decimal("0.00"),
                closing_balance=Decimal("0.00"),
            )
        )

    await session.flush()
    await _recompute_weeks(session, run)
    return run


async def update_week_assumptions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
    week_number: int,
    assumption_updates: dict,
) -> CashFlowForecastAssumption:
    run = await _get_run(session, tenant_id, forecast_run_id)
    row = (
        await session.execute(
            select(CashFlowForecastAssumption).where(
                CashFlowForecastAssumption.forecast_run_id == run.id,
                CashFlowForecastAssumption.tenant_id == tenant_id,
                CashFlowForecastAssumption.week_number == week_number,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Forecast week not found")

    mutable_fields = {
        "customer_collections",
        "other_inflows",
        "supplier_payments",
        "payroll",
        "rent_and_utilities",
        "loan_repayments",
        "tax_payments",
        "capex",
        "other_outflows",
        "notes",
    }

    for key, value in assumption_updates.items():
        if key not in mutable_fields:
            continue
        if key == "notes":
            setattr(row, key, value)
        else:
            setattr(row, key, _d(value))

    await session.flush()
    rows = await _recompute_weeks(session, run)
    return next(item for item in rows if item.week_number == week_number)


async def get_forecast_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
) -> dict:
    run = await _get_run(session, tenant_id, forecast_run_id)
    rows = (
        await session.execute(
            select(CashFlowForecastAssumption)
            .where(
                CashFlowForecastAssumption.forecast_run_id == run.id,
                CashFlowForecastAssumption.tenant_id == tenant_id,
            )
            .order_by(CashFlowForecastAssumption.week_number)
        )
    ).scalars().all()

    if not rows:
        return {
            "run": run,
            "weeks": [],
            "opening_balance": _d(run.opening_cash_balance),
            "closing_balance_week_13": _d(run.opening_cash_balance),
            "minimum_balance": _d(run.opening_cash_balance),
            "minimum_balance_week": 0,
            "total_inflows": Decimal("0.00"),
            "total_outflows": Decimal("0.00"),
            "net_position": Decimal("0.00"),
            "is_cash_positive": True,
            "weeks_below_zero": [],
        }

    closing_week = rows[-1]
    min_row = min(rows, key=lambda item: _d(item.closing_balance))
    total_inflows = sum((_d(item.total_inflows) for item in rows), Decimal("0.00")).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    total_outflows = sum((_d(item.total_outflows) for item in rows), Decimal("0.00")).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    net_position = (total_inflows - total_outflows).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    weeks_below_zero = [item.week_number for item in rows if _d(item.closing_balance) < Decimal("0.00")]

    return {
        "run": run,
        "weeks": rows,
        "opening_balance": _d(run.opening_cash_balance),
        "closing_balance_week_13": _d(closing_week.closing_balance),
        "minimum_balance": _d(min_row.closing_balance),
        "minimum_balance_week": min_row.week_number,
        "total_inflows": total_inflows,
        "total_outflows": total_outflows,
        "net_position": net_position,
        "is_cash_positive": len(weeks_below_zero) == 0,
        "weeks_below_zero": weeks_below_zero,
    }


async def seed_from_historical(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
) -> list[CashFlowForecastAssumption]:
    run = await _get_run(session, tenant_id, forecast_run_id)
    rows = (
        await session.execute(
            select(CashFlowForecastAssumption)
            .where(CashFlowForecastAssumption.forecast_run_id == run.id)
            .order_by(CashFlowForecastAssumption.week_number)
        )
    ).scalars().all()

    claims = (
        await session.execute(
            select(ExpenseClaim).where(ExpenseClaim.tenant_id == tenant_id)
        )
    ).scalars().all()

    if not claims:
        await _recompute_weeks(session, run)
        return rows

    total_claims = sum((_d(claim.amount_inr) for claim in claims), Decimal("0.00"))
    payroll_claims = sum((_d(claim.amount_inr) for claim in claims if str(claim.category).lower() in {"payroll", "staff", "salary"}), Decimal("0.00"))
    supplier_claims = (total_claims - payroll_claims).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)

    weekly_supplier = (supplier_claims / _WEEKLY_DIVISOR).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    weekly_payroll = (payroll_claims / _WEEKLY_DIVISOR).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    weekly_collections = (total_claims / _WEEKLY_DIVISOR).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)

    for row in rows:
        row.customer_collections = weekly_collections
        row.supplier_payments = weekly_supplier
        row.payroll = weekly_payroll

    await session.flush()
    await _recompute_weeks(session, run)
    return rows


async def publish_forecast(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    forecast_run_id: uuid.UUID,
    published_by: uuid.UUID,
) -> CashFlowForecastRun:
    draft = await _get_run(session, tenant_id, forecast_run_id)
    if draft.status != "draft":
        raise ValidationError("Only draft forecasts can be published")

    async def _clone_assumptions(source_run_id: uuid.UUID, target_run_id: uuid.UUID) -> None:
        source_rows = (
            await session.execute(
                select(CashFlowForecastAssumption)
                .where(
                    CashFlowForecastAssumption.forecast_run_id == source_run_id,
                    CashFlowForecastAssumption.tenant_id == tenant_id,
                )
                .order_by(CashFlowForecastAssumption.week_number)
            )
        ).scalars().all()
        for row in source_rows:
            session.add(
                CashFlowForecastAssumption(
                    forecast_run_id=target_run_id,
                    tenant_id=tenant_id,
                    week_number=row.week_number,
                    week_start_date=row.week_start_date,
                    customer_collections=_d(row.customer_collections),
                    other_inflows=_d(row.other_inflows),
                    supplier_payments=_d(row.supplier_payments),
                    payroll=_d(row.payroll),
                    rent_and_utilities=_d(row.rent_and_utilities),
                    loan_repayments=_d(row.loan_repayments),
                    tax_payments=_d(row.tax_payments),
                    capex=_d(row.capex),
                    other_outflows=_d(row.other_outflows),
                    total_inflows=_d(row.total_inflows),
                    total_outflows=_d(row.total_outflows),
                    net_cash_flow=_d(row.net_cash_flow),
                    closing_balance=_d(row.closing_balance),
                    notes=row.notes,
                )
            )

    current_published = (
        await session.execute(
            select(CashFlowForecastRun)
            .where(
                CashFlowForecastRun.tenant_id == tenant_id,
                CashFlowForecastRun.status == "published",
            )
            .order_by(CashFlowForecastRun.created_at.desc(), CashFlowForecastRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if current_published is not None:
        superseded = CashFlowForecastRun(
            tenant_id=tenant_id,
            run_name=current_published.run_name,
            base_date=current_published.base_date,
            weeks=current_published.weeks,
            opening_cash_balance=_d(current_published.opening_cash_balance),
            currency=current_published.currency,
            status="superseded",
            is_published=False,
            created_by=published_by,
        )
        session.add(superseded)
        await session.flush()
        await _clone_assumptions(current_published.id, superseded.id)

    published = CashFlowForecastRun(
        tenant_id=tenant_id,
        run_name=draft.run_name,
        base_date=draft.base_date,
        weeks=draft.weeks,
        opening_cash_balance=_d(draft.opening_cash_balance),
        currency=draft.currency,
        status="published",
        is_published=True,
        created_by=published_by,
    )
    session.add(published)
    await session.flush()
    await _clone_assumptions(draft.id, published.id)
    await session.flush()
    return published


__all__ = [
    "create_forecast_run",
    "update_week_assumptions",
    "get_forecast_summary",
    "seed_from_historical",
    "publish_forecast",
]
