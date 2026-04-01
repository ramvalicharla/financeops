from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.analytics_layer import AnalyticsMetric, AnalyticsSnapshot
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.application.financial_statements_service import (
    get_balance_sheet,
    get_cash_flow_statement,
    get_profit_and_loss,
)
from financeops.modules.accounting_layer.application.trial_balance_service import get_trial_balance
from financeops.platform.db.models.entities import CpEntity

_ZERO = Decimal("0")


@dataclass(frozen=True)
class ResolvedScope:
    entity_ids: list[uuid.UUID]
    as_of_date: date
    from_date: date
    to_date: date
    scope_dimension: dict[str, Any]


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _safe_pct(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == _ZERO:
        return None
    return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.000001"))


def variance_payload(current: Decimal, previous: Decimal) -> tuple[Decimal, Decimal | None]:
    variance_value = current - previous
    return variance_value, _safe_pct(current, previous)


async def resolve_scope(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    as_of_date: date | None,
    from_date: date | None,
    to_date: date | None,
) -> ResolvedScope:
    if org_entity_id is None and org_group_id is None:
        raise ValidationError("Provide org_entity_id or org_group_id.")

    if as_of_date is None:
        as_of_date = date.today()
    if from_date is None:
        from_date = _month_start(as_of_date)
    if to_date is None:
        to_date = as_of_date
    if from_date > to_date:
        raise ValidationError("from_date cannot be after to_date.")

    if org_entity_id is not None:
        rows = (
            await db.execute(
                select(CpEntity.id).where(
                    CpEntity.id == org_entity_id,
                    CpEntity.tenant_id == tenant_id,
                )
            )
        ).scalars().all()
        if not rows:
            raise ValidationError("org_entity_id does not belong to tenant.")
        entity_ids = [org_entity_id]
        dimension = {"org_entity_id": str(org_entity_id)}
    else:
        rows = (
            await db.execute(
                select(CpEntity.id).where(
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.group_id == org_group_id,
                )
            )
        ).scalars().all()
        if not rows:
            raise ValidationError("No entities found for org_group_id.")
        entity_ids = list(rows)
        dimension = {"org_group_id": str(org_group_id)}

    return ResolvedScope(
        entity_ids=entity_ids,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
        scope_dimension=dimension,
    )


async def compute_statement_bundle(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    from_date: date,
    to_date: date,
    as_of_date: date,
) -> dict[str, Any]:
    tb = await get_trial_balance(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    pnl = await get_profit_and_loss(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity_id,
        from_date=from_date,
        to_date=to_date,
    )
    bs = await get_balance_sheet(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity_id,
        as_of_date=as_of_date,
    )
    cf = await get_cash_flow_statement(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity_id,
        from_date=from_date,
        to_date=to_date,
    )
    return {"tb": tb, "pnl": pnl, "bs": bs, "cf": cf}


async def create_snapshot(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    snapshot_type: str,
    as_of_date: date,
    period_from: date | None,
    period_to: date | None,
    data_json: dict[str, Any],
) -> AnalyticsSnapshot:
    row = AnalyticsSnapshot(
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        snapshot_type=snapshot_type,
        as_of_date=as_of_date,
        period_from=period_from,
        period_to=period_to,
        data_json=data_json,
    )
    db.add(row)
    await db.flush()
    return row


async def create_metric_rows(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metrics: dict[str, Decimal],
    dimension_json: dict[str, Any],
) -> None:
    for metric_name, metric_value in metrics.items():
        db.add(
            AnalyticsMetric(
                tenant_id=tenant_id,
                metric_name=metric_name,
                metric_value=metric_value,
                dimension_json=dimension_json,
            )
        )
    await db.flush()


async def aggregate_gl_for_period(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_ids: list[uuid.UUID],
    from_date: date,
    to_date: date,
) -> list[tuple[str, str, Decimal, Decimal]]:
    from_dt = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc)
    rows = await db.execute(
        select(
            GlEntry.account_code,
            GlEntry.account_name,
            func.coalesce(func.sum(GlEntry.debit_amount), _ZERO),
            func.coalesce(func.sum(GlEntry.credit_amount), _ZERO),
        ).where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.entity_id.in_(entity_ids),
            and_(
                GlEntry.created_at >= from_dt,
                GlEntry.created_at <= to_dt,
            ),
        ).group_by(
            GlEntry.account_code,
            GlEntry.account_name,
        )
    )
    payload: list[tuple[str, str, Decimal, Decimal]] = []
    for account_code, account_name, debit, credit in rows.all():
        payload.append((account_code, account_name, Decimal(str(debit)), Decimal(str(credit))))
    return payload
