from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.modules.tax_provision.models import TaxPosition, TaxProvisionRun
from financeops.platform.services.tenancy.entity_access import assert_entity_access

_MONEY = Decimal("0.01")
_RATE = Decimal("0.0001")


def _money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _rate(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.0000")
    return Decimal(str(value)).quantize(_RATE, rounding=ROUND_HALF_UP)


def _fiscal_year_from_period(period: str) -> int:
    parts = period.split("-")
    if len(parts) != 2:
        raise ValidationError("period must be YYYY-MM")
    return int(parts[0])


async def _profit_before_tax(session: AsyncSession, tenant_id: uuid.UUID, fiscal_year: int) -> Decimal:
    version = (
        await session.execute(
            select(BudgetVersion)
            .where(BudgetVersion.tenant_id == tenant_id, BudgetVersion.fiscal_year == fiscal_year)
            .order_by(desc(BudgetVersion.created_at), desc(BudgetVersion.id))
        )
    ).scalars().first()

    if version is None:
        return Decimal("0.00")

    total = (
        await session.execute(
            select(func.coalesce(func.sum(BudgetLineItem.annual_total), 0))
            .where(
                BudgetLineItem.tenant_id == tenant_id,
                BudgetLineItem.budget_version_id == version.id,
            )
        )
    ).scalar_one()
    return _money(total)


async def upsert_tax_position(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    position_name: str,
    position_type: str,
    carrying_amount: Decimal,
    tax_base: Decimal,
    is_asset: bool,
    tax_rate: Decimal,
    description: str | None = None,
) -> TaxPosition:
    now = datetime.now(UTC)
    carrying = _money(carrying_amount)
    base = _money(tax_base)
    temp_diff = (carrying - base).quantize(_MONEY, rounding=ROUND_HALF_UP)
    impact = (temp_diff * _rate(tax_rate)).quantize(_MONEY, rounding=ROUND_HALF_UP)

    row = (
        await session.execute(
            select(TaxPosition).where(
                TaxPosition.tenant_id == tenant_id,
                TaxPosition.position_name == position_name,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = TaxPosition(
            tenant_id=tenant_id,
            position_name=position_name,
            position_type=position_type,
            carrying_amount=carrying,
            tax_base=base,
            temporary_difference=temp_diff,
            deferred_tax_impact=impact,
            is_asset=is_asset,
            description=description,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.position_type = position_type
        row.carrying_amount = carrying
        row.tax_base = base
        row.temporary_difference = temp_diff
        row.deferred_tax_impact = impact
        row.is_asset = is_asset
        row.description = description
        row.updated_at = now

    await session.flush()
    return row


async def compute_tax_provision(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    entity_id: uuid.UUID | None,
    applicable_tax_rate: Decimal,
    created_by: uuid.UUID,
    requester_user_id: uuid.UUID | None = None,
    requester_user_role: str | None = None,
) -> TaxProvisionRun:
    if entity_id is not None and requester_user_id is not None and requester_user_role is not None:
        await assert_entity_access(
            session=session,
            tenant_id=tenant_id,
            entity_id=entity_id,
            user_id=requester_user_id,
            user_role=requester_user_role,
        )
    fiscal_year = _fiscal_year_from_period(period)
    tax_rate = _rate(applicable_tax_rate)

    profit_before_tax = await _profit_before_tax(session, tenant_id, fiscal_year)

    positions = (
        await session.execute(
            select(TaxPosition).where(TaxPosition.tenant_id == tenant_id)
        )
    ).scalars().all()

    permanent_diff = sum(
        (_money(row.temporary_difference) for row in positions if row.position_type == "permanent_difference"),
        Decimal("0.00"),
    ).quantize(_MONEY, rounding=ROUND_HALF_UP)

    timing_diff = sum(
        (_money(row.temporary_difference) for row in positions if row.position_type in {"temporary_difference", "tax_loss_carryforward", "tax_credit"}),
        Decimal("0.00"),
    ).quantize(_MONEY, rounding=ROUND_HALF_UP)

    taxable_income = (profit_before_tax + permanent_diff + timing_diff).quantize(_MONEY, rounding=ROUND_HALF_UP)
    current_tax = (taxable_income * tax_rate).quantize(_MONEY, rounding=ROUND_HALF_UP)

    dta = sum(
        ((_money(row.temporary_difference) * tax_rate).quantize(_MONEY, rounding=ROUND_HALF_UP)
         for row in positions if row.is_asset),
        Decimal("0.00"),
    ).quantize(_MONEY, rounding=ROUND_HALF_UP)

    dtl = sum(
        ((_money(row.temporary_difference) * tax_rate).quantize(_MONEY, rounding=ROUND_HALF_UP)
         for row in positions if not row.is_asset),
        Decimal("0.00"),
    ).quantize(_MONEY, rounding=ROUND_HALF_UP)

    net_deferred = (dta - dtl).quantize(_MONEY, rounding=ROUND_HALF_UP)
    total_tax = (current_tax + net_deferred).quantize(_MONEY, rounding=ROUND_HALF_UP)

    if profit_before_tax == Decimal("0.00"):
        effective_rate = Decimal("0.0000")
    else:
        effective_rate = (total_tax / profit_before_tax).quantize(_RATE, rounding=ROUND_HALF_UP)

    row = TaxProvisionRun(
        tenant_id=tenant_id,
        entity_id=entity_id,
        period=period,
        fiscal_year=fiscal_year,
        applicable_tax_rate=tax_rate,
        accounting_profit_before_tax=profit_before_tax,
        permanent_differences=permanent_diff,
        timing_differences=timing_diff,
        taxable_income=taxable_income,
        current_tax_expense=current_tax,
        deferred_tax_asset=dta,
        deferred_tax_liability=dtl,
        net_deferred_tax=net_deferred,
        total_tax_expense=total_tax,
        effective_tax_rate=effective_rate,
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def get_tax_provision_schedule(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
) -> dict:
    periods = (
        await session.execute(
            select(TaxProvisionRun)
            .where(
                TaxProvisionRun.tenant_id == tenant_id,
                TaxProvisionRun.fiscal_year == fiscal_year,
            )
            .order_by(TaxProvisionRun.period)
        )
    ).scalars().all()

    positions = (
        await session.execute(
            select(TaxPosition)
            .where(TaxPosition.tenant_id == tenant_id)
            .order_by(TaxPosition.position_name)
        )
    ).scalars().all()

    ytd_current_tax = sum((_money(row.current_tax_expense) for row in periods), Decimal("0.00")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    ytd_deferred_tax = sum((_money(row.net_deferred_tax) for row in periods), Decimal("0.00")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    ytd_total_tax = (ytd_current_tax + ytd_deferred_tax).quantize(_MONEY, rounding=ROUND_HALF_UP)

    profit_sum = sum((_money(row.accounting_profit_before_tax) for row in periods), Decimal("0.00")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    effective_tax_rate_ytd = Decimal("0.0000") if profit_sum == Decimal("0.00") else (ytd_total_tax / profit_sum).quantize(_RATE, rounding=ROUND_HALF_UP)

    return {
        "fiscal_year": fiscal_year,
        "periods": periods,
        "ytd_current_tax": ytd_current_tax,
        "ytd_deferred_tax": ytd_deferred_tax,
        "ytd_total_tax": ytd_total_tax,
        "effective_tax_rate_ytd": effective_tax_rate_ytd,
        "deferred_tax_positions": positions,
    }


async def get_provision_for_period(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
) -> TaxProvisionRun:
    row = (
        await session.execute(
            select(TaxProvisionRun)
            .where(
                TaxProvisionRun.tenant_id == tenant_id,
                TaxProvisionRun.period == period,
            )
            .order_by(desc(TaxProvisionRun.created_at), desc(TaxProvisionRun.id))
        )
    ).scalars().first()
    if row is None:
        raise NotFoundError("Tax provision not found for period")
    return row


async def list_tax_positions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(TaxPosition)
                .where(TaxPosition.tenant_id == tenant_id)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(TaxPosition)
            .where(TaxPosition.tenant_id == tenant_id)
            .order_by(desc(TaxPosition.updated_at), desc(TaxPosition.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"total": total, "data": rows, "limit": limit, "offset": offset}


__all__ = [
    "compute_tax_provision",
    "get_tax_provision_schedule",
    "get_provision_for_period",
    "list_tax_positions",
    "upsert_tax_position",
]
