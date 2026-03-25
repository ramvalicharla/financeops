from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.mis_manager import MisUpload
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.platform.services.tenancy.entity_access import assert_entity_access

MONTH_COLUMNS = (
    "month_01",
    "month_02",
    "month_03",
    "month_04",
    "month_05",
    "month_06",
    "month_07",
    "month_08",
    "month_09",
    "month_10",
    "month_11",
    "month_12",
)


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _month_index_from_period(period: str) -> int:
    try:
        _, month_str = str(period).split("-", 1)
        month = int(month_str)
    except (TypeError, ValueError) as exc:
        raise ValidationError("period must be in YYYY-MM format") from exc
    if month < 1 or month > 12:
        raise ValidationError("period month must be between 01 and 12")
    return month


def _as_decimal(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value))


async def _load_budget_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    budget_version_id: uuid.UUID,
) -> BudgetVersion:
    version = (
        await session.execute(
            select(BudgetVersion).where(
                BudgetVersion.id == budget_version_id,
                BudgetVersion.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFoundError("Budget version not found")
    return version


async def _load_actuals_map(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    fiscal_year: int,
) -> dict[tuple[str, int], Decimal]:
    rows = (
        await session.execute(
            select(MisUpload).where(
                MisUpload.tenant_id == tenant_id,
                MisUpload.period_year == fiscal_year,
            )
        )
    ).scalars().all()

    values: dict[tuple[str, int], Decimal] = {}
    for row in rows:
        parsed = row.parsed_data if isinstance(row.parsed_data, dict) else {}
        actuals = parsed.get("actuals")
        if isinstance(actuals, dict):
            for key, amount in actuals.items():
                values[(str(key), int(row.period_month))] = _q2(_as_decimal(amount))

        lines = parsed.get("lines")
        if isinstance(lines, list):
            for item in lines:
                if not isinstance(item, dict):
                    continue
                line_name = str(item.get("mis_line_item") or "")
                amount = item.get("amount")
                if not line_name or amount is None:
                    continue
                values[(line_name, int(row.period_month))] = _q2(_as_decimal(amount))
    return values


async def create_budget_version(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    version_name: str,
    created_by: uuid.UUID,
    copy_from_version_id: uuid.UUID | None = None,
) -> BudgetVersion:
    """
    Create a new budget version for the fiscal year.
    If copy_from_version_id provided: copy all line items
    from that version as starting point (new append-only records).
    Auto-increments version_number within tenant+fiscal_year.
    """
    max_version = (
        await session.execute(
            select(func.max(BudgetVersion.version_number)).where(
                BudgetVersion.tenant_id == tenant_id,
                BudgetVersion.fiscal_year == fiscal_year,
            )
        )
    ).scalar_one()
    next_version = int(max_version or 0) + 1

    version = BudgetVersion(
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        version_name=version_name,
        version_number=next_version,
        status="draft",
        created_by=created_by,
    )
    session.add(version)
    await session.flush()

    if copy_from_version_id is not None:
        source = await _load_budget_version(
            session,
            tenant_id=tenant_id,
            budget_version_id=copy_from_version_id,
        )
        source_lines = (
            await session.execute(
                select(BudgetLineItem).where(
                    BudgetLineItem.tenant_id == tenant_id,
                    BudgetLineItem.budget_version_id == source.id,
                )
            )
        ).scalars().all()

        for line in source_lines:
            session.add(
                BudgetLineItem(
                    budget_version_id=version.id,
                    tenant_id=tenant_id,
                    entity_id=line.entity_id,
                    mis_line_item=line.mis_line_item,
                    mis_category=line.mis_category,
                    month_01=line.month_01,
                    month_02=line.month_02,
                    month_03=line.month_03,
                    month_04=line.month_04,
                    month_05=line.month_05,
                    month_06=line.month_06,
                    month_07=line.month_07,
                    month_08=line.month_08,
                    month_09=line.month_09,
                    month_10=line.month_10,
                    month_11=line.month_11,
                    month_12=line.month_12,
                    basis=line.basis,
                )
            )
        await session.flush()

    return version


async def upsert_budget_line(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    budget_version_id: uuid.UUID,
    mis_line_item: str,
    mis_category: str,
    monthly_values: list[Decimal],
    basis: str | None = None,
    entity_id: uuid.UUID | None = None,
    requester_user_id: uuid.UUID | None = None,
    requester_user_role: str | None = None,
) -> BudgetLineItem:
    """
    Insert a new budget line item (append-only).
    monthly_values must be list of exactly 12 Decimal values.
    Validates: all values are Decimal, none are negative for
    revenue lines without explicit justification.
    """
    await _load_budget_version(
        session,
        tenant_id=tenant_id,
        budget_version_id=budget_version_id,
    )
    if entity_id is not None and requester_user_id is not None and requester_user_role is not None:
        await assert_entity_access(
            session=session,
            tenant_id=tenant_id,
            entity_id=entity_id,
            user_id=requester_user_id,
            user_role=requester_user_role,
        )
    if len(monthly_values) != 12:
        raise ValueError("monthly_values must contain exactly 12 values")

    normalized: list[Decimal] = []
    for value in monthly_values:
        decimal_value = _as_decimal(value)
        if "revenue" in mis_category.lower() and decimal_value < Decimal("0") and not str(basis or "").strip():
            raise ValidationError("negative revenue budget requires basis justification")
        normalized.append(_q2(decimal_value))

    record = BudgetLineItem(
        budget_version_id=budget_version_id,
        tenant_id=tenant_id,
        entity_id=entity_id,
        mis_line_item=mis_line_item,
        mis_category=mis_category,
        month_01=normalized[0],
        month_02=normalized[1],
        month_03=normalized[2],
        month_04=normalized[3],
        month_05=normalized[4],
        month_06=normalized[5],
        month_07=normalized[6],
        month_08=normalized[7],
        month_09=normalized[8],
        month_10=normalized[9],
        month_11=normalized[10],
        month_12=normalized[11],
        basis=basis,
    )
    session.add(record)
    await session.flush()
    return record


async def approve_budget(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    budget_version_id: uuid.UUID,
    approved_by: uuid.UUID,
) -> BudgetVersion:
    """
    Mark budget as board-approved and supersede prior approved version.
    """
    target = await _load_budget_version(
        session,
        tenant_id=tenant_id,
        budget_version_id=budget_version_id,
    )
    now = datetime.now(UTC)

    await session.execute(
        update(BudgetVersion)
        .where(
            BudgetVersion.tenant_id == tenant_id,
            BudgetVersion.fiscal_year == target.fiscal_year,
            BudgetVersion.id != target.id,
            BudgetVersion.status == "approved",
        )
        .values(status="superseded", updated_at=now)
    )

    target.status = "approved"
    target.is_board_approved = True
    target.board_approved_by = approved_by
    target.board_approved_at = now
    target.updated_at = now
    await session.flush()
    return target


async def get_budget_vs_actual(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    period: str,
    budget_version_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    requester_user_id: uuid.UUID | None = None,
    requester_user_role: str | None = None,
) -> dict:
    """
    Compare approved budget to actual MIS data.
    """
    month_idx = _month_index_from_period(period)
    if entity_id is not None and requester_user_id is not None and requester_user_role is not None:
        await assert_entity_access(
            session=session,
            tenant_id=tenant_id,
            entity_id=entity_id,
            user_id=requester_user_id,
            user_role=requester_user_role,
        )
    if budget_version_id is not None:
        version = await _load_budget_version(
            session,
            tenant_id=tenant_id,
            budget_version_id=budget_version_id,
        )
    else:
        version = (
            await session.execute(
                select(BudgetVersion)
                .where(
                    BudgetVersion.tenant_id == tenant_id,
                    BudgetVersion.fiscal_year == fiscal_year,
                    BudgetVersion.status == "approved",
                )
                .order_by(desc(BudgetVersion.version_number))
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            version = (
                await session.execute(
                    select(BudgetVersion)
                    .where(
                        BudgetVersion.tenant_id == tenant_id,
                        BudgetVersion.fiscal_year == fiscal_year,
                    )
                    .order_by(desc(BudgetVersion.version_number))
                    .limit(1)
                )
            ).scalar_one_or_none()
    if version is None:
        raise NotFoundError("No budget version found")

    stmt = select(BudgetLineItem).where(
        BudgetLineItem.tenant_id == tenant_id,
        BudgetLineItem.budget_version_id == version.id,
    )
    if entity_id is not None:
        stmt = stmt.where(BudgetLineItem.entity_id == entity_id)

    lines = (await session.execute(stmt.order_by(BudgetLineItem.mis_category, BudgetLineItem.mis_line_item))).scalars().all()
    actuals_map = await _load_actuals_map(session, tenant_id=tenant_id, fiscal_year=fiscal_year)

    response_lines: list[dict] = []
    total_revenue_budget = Decimal("0")
    total_revenue_actual = Decimal("0")
    ebitda_budget = Decimal("0")
    ebitda_actual = Decimal("0")

    for row in lines:
        monthly_budget = [_q2(_as_decimal(getattr(row, column))) for column in MONTH_COLUMNS]
        budget_ytd = _q2(sum(monthly_budget[:month_idx], start=Decimal("0")))
        monthly_payload: list[dict] = []
        actual_ytd = Decimal("0")

        for i in range(1, month_idx + 1):
            month_key = f"{fiscal_year:04d}-{i:02d}"
            budget_value = monthly_budget[i - 1]
            actual_value = _q2(actuals_map.get((row.mis_line_item, i), Decimal("0")))
            actual_ytd += actual_value
            monthly_payload.append(
                {
                    "month": month_key,
                    "budget": budget_value,
                    "actual": actual_value,
                    "variance": _q2(actual_value - budget_value),
                }
            )

        actual_ytd = _q2(actual_ytd)
        variance_amount = _q2(actual_ytd - budget_ytd)
        variance_pct = Decimal("0")
        if budget_ytd != Decimal("0"):
            variance_pct = _q4((variance_amount / budget_ytd) * Decimal("100"))

        if row.mis_category == "Revenue":
            total_revenue_budget += budget_ytd
            total_revenue_actual += actual_ytd
        if row.mis_category == "EBITDA" or "ebitda" in row.mis_line_item.lower():
            ebitda_budget += budget_ytd
            ebitda_actual += actual_ytd

        response_lines.append(
            {
                "mis_line_item": row.mis_line_item,
                "mis_category": row.mis_category,
                "budget_ytd": budget_ytd,
                "actual_ytd": actual_ytd,
                "variance_amount": variance_amount,
                "variance_pct": variance_pct,
                "budget_full_year": _q2(_as_decimal(row.annual_total)),
                "monthly": monthly_payload,
            }
        )

    revenue_variance_pct = Decimal("0")
    if total_revenue_budget != Decimal("0"):
        revenue_variance_pct = _q4(((total_revenue_actual - total_revenue_budget) / total_revenue_budget) * Decimal("100"))

    return {
        "fiscal_year": fiscal_year,
        "period_through": period,
        "version_id": str(version.id),
        "lines": response_lines,
        "summary": {
            "total_revenue_budget": _q2(total_revenue_budget),
            "total_revenue_actual": _q2(total_revenue_actual),
            "ebitda_budget": _q2(ebitda_budget),
            "ebitda_actual": _q2(ebitda_actual),
            "on_budget": abs(revenue_variance_pct) <= Decimal("5.0000"),
        },
    }


async def get_budget_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
) -> list[BudgetVersion]:
    """
    Returns all budget versions for fiscal_year, ordered by version_number DESC.
    """
    return (
        await session.execute(
            select(BudgetVersion)
            .where(
                BudgetVersion.tenant_id == tenant_id,
                BudgetVersion.fiscal_year == fiscal_year,
            )
            .order_by(desc(BudgetVersion.version_number))
        )
    ).scalars().all()
