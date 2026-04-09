from __future__ import annotations

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.db.models.working_capital import WorkingCapitalSnapshot
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)

_SAFE_PRECISION = Decimal("0.0001")


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return numerator/denominator or 0 if denominator is zero."""
    if denominator == Decimal("0"):
        return Decimal("0")
    return (numerator / denominator).quantize(_SAFE_PRECISION, rounding=ROUND_HALF_UP)


async def create_snapshot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    created_by: uuid.UUID,
    cash_and_equivalents: Decimal = Decimal("0"),
    accounts_receivable: Decimal = Decimal("0"),
    inventory: Decimal = Decimal("0"),
    prepaid_expenses: Decimal = Decimal("0"),
    other_current_assets: Decimal = Decimal("0"),
    accounts_payable: Decimal = Decimal("0"),
    accrued_liabilities: Decimal = Decimal("0"),
    short_term_debt: Decimal = Decimal("0"),
    other_current_liabilities: Decimal = Decimal("0"),
    currency: str = "USD",
    notes: str | None = None,
) -> WorkingCapitalSnapshot:
    """
    Compute working capital metrics and store as an immutable snapshot (INSERT ONLY).
    All ratios are computed at write time from the supplied components.
    """
    require_mutation_context("Working capital snapshot creation")
    total_current_assets = (
        cash_and_equivalents
        + accounts_receivable
        + inventory
        + prepaid_expenses
        + other_current_assets
    )
    total_current_liabilities = (
        accounts_payable
        + accrued_liabilities
        + short_term_debt
        + other_current_liabilities
    )
    working_capital = total_current_assets - total_current_liabilities
    current_ratio = _safe_ratio(total_current_assets, total_current_liabilities)
    quick_ratio = _safe_ratio(
        total_current_assets - inventory, total_current_liabilities
    )
    cash_ratio = _safe_ratio(cash_and_equivalents, total_current_liabilities)

    previous_hash = await get_previous_hash_locked(session, WorkingCapitalSnapshot, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "period_year": period_year,
        "period_month": period_month,
        "entity_name": entity_name,
        "total_current_assets": str(total_current_assets),
        "total_current_liabilities": str(total_current_liabilities),
        "working_capital": str(working_capital),
        "created_by": str(created_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    snap = apply_mutation_linkage(WorkingCapitalSnapshot(
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        currency=currency,
        cash_and_equivalents=cash_and_equivalents,
        accounts_receivable=accounts_receivable,
        inventory=inventory,
        prepaid_expenses=prepaid_expenses,
        other_current_assets=other_current_assets,
        total_current_assets=total_current_assets,
        accounts_payable=accounts_payable,
        accrued_liabilities=accrued_liabilities,
        short_term_debt=short_term_debt,
        other_current_liabilities=other_current_liabilities,
        total_current_liabilities=total_current_liabilities,
        working_capital=working_capital,
        current_ratio=current_ratio,
        quick_ratio=quick_ratio,
        cash_ratio=cash_ratio,
        created_by=created_by,
        notes=notes,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    ))
    session.add(snap)
    await session.flush()
    log.info(
        "WorkingCapital snapshot: tenant=%s entity=%s period=%d/%d wc=%s",
        str(tenant_id)[:8], entity_name, period_year, period_month, working_capital,
    )
    return snap


async def list_snapshots(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_name: str | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[WorkingCapitalSnapshot]:
    stmt = select(WorkingCapitalSnapshot).where(WorkingCapitalSnapshot.tenant_id == tenant_id)
    if entity_name:
        stmt = stmt.where(WorkingCapitalSnapshot.entity_name == entity_name)
    if period_year is not None:
        stmt = stmt.where(WorkingCapitalSnapshot.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(WorkingCapitalSnapshot.period_month == period_month)
    stmt = stmt.order_by(
        desc(WorkingCapitalSnapshot.period_year),
        desc(WorkingCapitalSnapshot.period_month),
    ).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_latest_snapshot(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_name: str,
) -> WorkingCapitalSnapshot | None:
    result = await session.execute(
        select(WorkingCapitalSnapshot)
        .where(
            WorkingCapitalSnapshot.tenant_id == tenant_id,
            WorkingCapitalSnapshot.entity_name == entity_name,
        )
        .order_by(
            desc(WorkingCapitalSnapshot.period_year),
            desc(WorkingCapitalSnapshot.period_month),
            desc(WorkingCapitalSnapshot.created_at),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()

