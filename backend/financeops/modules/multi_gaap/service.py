from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.modules.budgeting.models import BudgetLineItem
from financeops.modules.multi_gaap.models import MultiGAAPConfig, MultiGAAPRun
from financeops.platform.db.models.entities import CpEntity

_MONEY = Decimal("0.01")
_PCT = Decimal("0.0001")


def _money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _percent_diff(value: Decimal, base: Decimal) -> Decimal:
    if base == Decimal("0.00"):
        return Decimal("0.0000")
    return ((value / base) * Decimal("100")).quantize(_PCT, rounding=ROUND_HALF_UP)


async def _resolve_entity_id(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    resolved = (
        await session.execute(
            select(CpEntity.id)
            .where(
                CpEntity.tenant_id == tenant_id,
                CpEntity.status == "active",
            )
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if resolved is not None:
        return resolved
    fallback = (
        await session.execute(
            select(CpEntity.id)
            .where(CpEntity.status == "active")
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if fallback is None:
        raise ValueError("No active entity available")
    return fallback


async def get_or_create_config(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
) -> MultiGAAPConfig:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    row = (
        await session.execute(
            select(MultiGAAPConfig).where(
                MultiGAAPConfig.tenant_id == tenant_id,
                MultiGAAPConfig.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    require_mutation_context("Multi-GAAP config creation")
    now = datetime.now(UTC)
    row = MultiGAAPConfig(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        primary_gaap="INDAS",
        secondary_gaaps=[],
        revenue_recognition_policy={},
        lease_classification_policy={},
        financial_instruments_policy={},
        created_at=now,
        updated_at=now,
    )
    apply_mutation_linkage(row)
    session.add(row)
    await session.flush()
    return row


async def update_config(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    updates: dict,
    entity_id: uuid.UUID | None = None,
) -> MultiGAAPConfig:
    require_mutation_context("Multi-GAAP config update")
    row = await get_or_create_config(session, tenant_id, entity_id=entity_id)
    for key in {
        "primary_gaap",
        "secondary_gaaps",
        "revenue_recognition_policy",
        "lease_classification_policy",
        "financial_instruments_policy",
    }:
        if key in updates:
            setattr(row, key, updates[key])
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def _base_financials(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    period: str,
) -> dict[str, Decimal]:
    del period
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    annual_total = (
        await session.execute(
            select(func.coalesce(func.sum(BudgetLineItem.annual_total), 0)).where(BudgetLineItem.tenant_id == tenant_id)
            .where(BudgetLineItem.entity_id == resolved_entity_id)
        )
    ).scalar_one()
    revenue = _money(annual_total)
    if revenue == Decimal("0.00"):
        revenue = Decimal("1000.00")

    gross_profit = (revenue * Decimal("0.55")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    ebitda = (revenue * Decimal("0.18")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    depreciation = (revenue * Decimal("0.04")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    ebit = (ebitda - depreciation).quantize(_MONEY, rounding=ROUND_HALF_UP)
    profit_before_tax = (ebit - (revenue * Decimal("0.03")).quantize(_MONEY, rounding=ROUND_HALF_UP)).quantize(_MONEY, rounding=ROUND_HALF_UP)
    profit_after_tax = (profit_before_tax * Decimal("0.75")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    total_assets = (revenue * Decimal("1.30")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    total_equity = (revenue * Decimal("0.70")).quantize(_MONEY, rounding=ROUND_HALF_UP)

    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "ebitda": ebitda,
        "depreciation": depreciation,
        "ebit": ebit,
        "profit_before_tax": profit_before_tax,
        "profit_after_tax": profit_after_tax,
        "total_assets": total_assets,
        "total_equity": total_equity,
    }


async def compute_gaap_view(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    gaap_framework: str,
    created_by: uuid.UUID,
    entity_id: uuid.UUID | None = None,
) -> MultiGAAPRun:
    require_mutation_context("Multi-GAAP view computation")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    config = await get_or_create_config(session, tenant_id, entity_id=resolved_entity_id)
    base = await _base_financials(session, tenant_id, resolved_entity_id, period)

    adjustments: list[dict] = []
    revenue = base["revenue"]
    gross_profit = base["gross_profit"]
    ebitda = base["ebitda"]
    ebit = base["ebit"]
    pbt = base["profit_before_tax"]
    pat = base["profit_after_tax"]
    assets = base["total_assets"]
    equity = base["total_equity"]

    framework = gaap_framework.upper()
    if framework == "MANAGEMENT":
        add_back_da = base["depreciation"]
        one_time_addback = (base["revenue"] * Decimal("0.01")).quantize(_MONEY, rounding=ROUND_HALF_UP)
        ebitda = (ebitda + add_back_da + one_time_addback).quantize(_MONEY, rounding=ROUND_HALF_UP)
        pbt = (pbt + one_time_addback).quantize(_MONEY, rounding=ROUND_HALF_UP)
        pat = (pbt * Decimal("0.75")).quantize(_MONEY, rounding=ROUND_HALF_UP)
        adjustments.extend(
            [
                {"description": "Add back depreciation and amortisation", "amount": str(add_back_da), "line_item": "EBITDA"},
                {"description": "Add back one-time items", "amount": str(one_time_addback), "line_item": "EBITDA"},
            ]
        )
    elif framework in {"IFRS", "USGAAP"}:
        policy_map = config.financial_instruments_policy or {}
        policy_adjustment = _money(policy_map.get(framework, "0")) if isinstance(policy_map, dict) else Decimal("0.00")
        if policy_adjustment != Decimal("0.00"):
            revenue = (revenue + policy_adjustment).quantize(_MONEY, rounding=ROUND_HALF_UP)
            gross_profit = (gross_profit + policy_adjustment).quantize(_MONEY, rounding=ROUND_HALF_UP)
            pbt = (pbt + policy_adjustment).quantize(_MONEY, rounding=ROUND_HALF_UP)
            pat = (pbt * Decimal("0.75")).quantize(_MONEY, rounding=ROUND_HALF_UP)
            adjustments.append(
                {"description": f"{framework} policy adjustment", "amount": str(policy_adjustment), "line_item": "Revenue"}
            )

    table = MultiGAAPRun.__table__
    stmt = insert(table).values(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        period=period,
        gaap_framework=framework,
        revenue=revenue,
        gross_profit=gross_profit,
        ebitda=ebitda,
        ebit=ebit,
        profit_before_tax=pbt,
        profit_after_tax=pat,
        total_assets=assets,
        total_equity=equity,
        adjustments=adjustments,
        created_by=created_by,
        created_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_nothing(constraint="uq_multi_gaap_runs_tenant_entity_period_framework")
    await session.execute(stmt)
    await session.flush()

    row = (
        await session.execute(
            select(MultiGAAPRun).where(
                MultiGAAPRun.tenant_id == tenant_id,
                MultiGAAPRun.entity_id == resolved_entity_id,
                MultiGAAPRun.period == period,
                MultiGAAPRun.gaap_framework == framework,
            )
        )
    ).scalar_one()
    return row


async def get_gaap_comparison(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    entity_id: uuid.UUID | None = None,
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    rows = (
        await session.execute(
            select(MultiGAAPRun)
            .where(
                MultiGAAPRun.tenant_id == tenant_id,
                MultiGAAPRun.entity_id == resolved_entity_id,
                MultiGAAPRun.period == period,
            )
            .order_by(MultiGAAPRun.gaap_framework)
        )
    ).scalars().all()

    indas = next((row for row in rows if row.gaap_framework == "INDAS"), None)

    frameworks = [
        {
            "gaap_framework": row.gaap_framework,
            "revenue": _money(row.revenue),
            "gross_profit": _money(row.gross_profit),
            "ebitda": _money(row.ebitda),
            "profit_before_tax": _money(row.profit_before_tax),
            "profit_after_tax": _money(row.profit_after_tax),
            "adjustments": row.adjustments or [],
        }
        for row in rows
    ]

    differences: dict[str, dict[str, Decimal]] = {
        "revenue_vs_indas": {},
        "ebitda_vs_indas": {},
    }
    if indas is not None:
        for row in rows:
            if row.gaap_framework == "INDAS":
                continue
            differences["revenue_vs_indas"][row.gaap_framework] = (_money(row.revenue) - _money(indas.revenue)).quantize(_MONEY, rounding=ROUND_HALF_UP)
            differences["ebitda_vs_indas"][row.gaap_framework] = (_money(row.ebitda) - _money(indas.ebitda)).quantize(_MONEY, rounding=ROUND_HALF_UP)

    return {
        "period": period,
        "frameworks": frameworks,
        "differences": differences,
    }


async def get_specific_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    gaap_framework: str,
    period: str,
    entity_id: uuid.UUID | None = None,
) -> MultiGAAPRun | None:
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    return (
        await session.execute(
            select(MultiGAAPRun).where(
                MultiGAAPRun.tenant_id == tenant_id,
                MultiGAAPRun.entity_id == resolved_entity_id,
                MultiGAAPRun.gaap_framework == gaap_framework.upper(),
                MultiGAAPRun.period == period,
            )
        )
    ).scalar_one_or_none()


__all__ = [
    "get_or_create_config",
    "update_config",
    "compute_gaap_view",
    "get_gaap_comparison",
    "get_specific_run",
]
