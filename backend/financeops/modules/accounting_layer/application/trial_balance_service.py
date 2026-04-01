from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.domain.schemas import (
    TrialBalanceAccountRow,
    TrialBalanceResponse,
)
from financeops.platform.db.models.entities import CpEntity


async def get_trial_balance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    as_of_date: date,
    from_date: date | None = None,
    to_date: date | None = None,
) -> TrialBalanceResponse:
    await _assert_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
    )

    as_of_end = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
    lower_bound = (
        datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        if from_date is not None
        else None
    )
    upper_bound = (
        datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        if to_date is not None
        else None
    )
    effective_upper_bound = (
        min(upper_bound, as_of_end) if upper_bound is not None else as_of_end
    )

    stmt = (
        select(
            GlEntry.account_code,
            GlEntry.account_name,
            func.coalesce(func.sum(GlEntry.debit_amount), Decimal("0")).label("debit_sum"),
            func.coalesce(func.sum(GlEntry.credit_amount), Decimal("0")).label("credit_sum"),
        )
        .where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.entity_id == org_entity_id,
            GlEntry.created_at <= effective_upper_bound,
        )
        .group_by(GlEntry.account_code, GlEntry.account_name)
        .order_by(GlEntry.account_code.asc())
    )

    if lower_bound is not None:
        stmt = stmt.where(GlEntry.created_at >= lower_bound)

    result = await db.execute(stmt)
    rows_raw = result.all()

    rows: list[TrialBalanceAccountRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for account_code, account_name, debit_sum, credit_sum in rows_raw:
        debit = Decimal(str(debit_sum or "0"))
        credit = Decimal(str(credit_sum or "0"))
        total_debit += debit
        total_credit += credit
        rows.append(
            TrialBalanceAccountRow(
                account_code=account_code,
                account_name=account_name,
                debit_sum=debit,
                credit_sum=credit,
                balance=debit - credit,
            )
        )

    if total_debit != total_credit:
        raise ValidationError(
            f"Trial balance integrity failed: total_debit={total_debit}, total_credit={total_credit}."
        )

    return TrialBalanceResponse(
        org_entity_id=org_entity_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
        total_debit=total_debit,
        total_credit=total_credit,
        rows=rows,
    )


async def _assert_entity_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
) -> None:
    stmt = select(CpEntity.id).where(
        CpEntity.id == org_entity_id,
        CpEntity.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise ValidationError("Entity does not belong to tenant.")
