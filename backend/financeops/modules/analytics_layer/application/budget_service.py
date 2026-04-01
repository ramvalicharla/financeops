from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.analytics_layer import Budget
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.analytics_layer.application.common import create_snapshot
from financeops.modules.analytics_layer.schemas import BudgetVarianceResponse, BudgetVarianceRow
from financeops.modules.coa.models import TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity

_ZERO = Decimal("0")


def _safe_pct(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == _ZERO:
        return None
    return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.000001"))


async def get_budget_variance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    period: str,
) -> BudgetVarianceResponse:
    if len(period) != 7 or period[4] != "-":
        raise ValidationError("period must be in YYYY-MM format.")
    year = int(period[:4])
    month = int(period[5:])
    if month < 1 or month > 12:
        raise ValidationError("period month must be 01..12.")

    entity_exists = (
        await db.execute(
            select(CpEntity.id).where(
                CpEntity.id == org_entity_id,
                CpEntity.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if entity_exists is None:
        raise ValidationError("org_entity_id does not belong to tenant.")

    budget_rows = (
        await db.execute(
            select(Budget, TenantCoaAccount.account_code, TenantCoaAccount.display_name)
            .join(TenantCoaAccount, TenantCoaAccount.id == Budget.account_id)
            .where(
                Budget.tenant_id == tenant_id,
                Budget.org_entity_id == org_entity_id,
                Budget.period == period,
            )
            .order_by(TenantCoaAccount.account_code.asc())
        )
    ).all()

    gl_map: dict[str, Decimal] = {}
    gl_rows = (
        await db.execute(
            select(
                GlEntry.account_code,
                func.coalesce(func.sum(GlEntry.debit_amount), _ZERO).label("debit_sum"),
                func.coalesce(func.sum(GlEntry.credit_amount), _ZERO).label("credit_sum"),
            ).where(
                and_(
                    GlEntry.tenant_id == tenant_id,
                    GlEntry.entity_id == org_entity_id,
                    GlEntry.period_year == year,
                    GlEntry.period_month == month,
                )
            ).group_by(GlEntry.account_code)
        )
    ).all()
    for account_code, debit_sum, credit_sum in gl_rows:
        gl_map[account_code] = Decimal(str(debit_sum)) - Decimal(str(credit_sum))

    rows: list[BudgetVarianceRow] = []
    for budget, account_code, account_name in budget_rows:
        actual_amount = gl_map.get(account_code, _ZERO)
        variance_value = actual_amount - budget.budget_amount
        rows.append(
            BudgetVarianceRow(
                account_id=budget.account_id,
                account_code=account_code,
                account_name=account_name,
                budget_amount=budget.budget_amount,
                actual_amount=actual_amount,
                variance_value=variance_value,
                variance_percent=_safe_pct(actual_amount, budget.budget_amount),
            )
        )

    snapshot = await create_snapshot(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=None,
        snapshot_type="TB",
        as_of_date=datetime.now(tz=timezone.utc).date(),
        period_from=None,
        period_to=None,
        data_json={
            "period": period,
            "row_count": len(rows),
            "rows": [row.model_dump(mode="json") for row in rows[:300]],
        },
    )
    await db.flush()

    return BudgetVarianceResponse(
        period=period,
        org_entity_id=org_entity_id,
        rows=rows,
        snapshot={
            "snapshot_id": snapshot.id,
            "snapshot_type": snapshot.snapshot_type,
            "as_of_date": snapshot.as_of_date,
            "period_from": snapshot.period_from,
            "period_to": snapshot.period_to,
        },
    )

