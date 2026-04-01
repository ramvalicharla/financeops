from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.ai_cfo_layer.schemas import (
    SuggestedJournal,
    SuggestedJournalLine,
    SuggestionsResponse,
)
from financeops.modules.analytics_layer.application.common import resolve_scope
from financeops.modules.analytics_layer.application.variance_service import compute_variance

_ZERO = Decimal("0")


def _month_bounds(anchor: date) -> tuple[datetime, datetime]:
    from_dt = datetime.combine(date(anchor.year, anchor.month, 1), time.min, tzinfo=timezone.utc)
    if anchor.month == 12:
        next_month = date(anchor.year + 1, 1, 1)
    else:
        next_month = date(anchor.year, anchor.month + 1, 1)
    to_dt = datetime.combine(next_month - timedelta(days=1), time.max, tzinfo=timezone.utc)
    return from_dt, to_dt


def _previous_month(anchor: date) -> date:
    if anchor.month == 1:
        return date(anchor.year - 1, 12, 1)
    return date(anchor.year, anchor.month - 1, 1)


async def _gl_net_by_account(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_ids: list[uuid.UUID],
    from_dt: datetime,
    to_dt: datetime,
) -> dict[str, tuple[str, Decimal]]:
    result = (
        await db.execute(
            select(
                GlEntry.account_code,
                GlEntry.account_name,
                func.coalesce(func.sum(GlEntry.debit_amount), _ZERO).label("debit_sum"),
                func.coalesce(func.sum(GlEntry.credit_amount), _ZERO).label("credit_sum"),
            ).where(
                and_(
                    GlEntry.tenant_id == tenant_id,
                    GlEntry.entity_id.in_(entity_ids),
                    GlEntry.created_at >= from_dt,
                    GlEntry.created_at <= to_dt,
                )
            ).group_by(GlEntry.account_code, GlEntry.account_name).order_by(GlEntry.account_code.asc())
        )
    ).all()

    payload: dict[str, tuple[str, Decimal]] = {}
    for account_code, account_name, debit_sum, credit_sum in result:
        payload[account_code] = (
            account_name,
            Decimal(str(debit_sum)) - Decimal(str(credit_sum)),
        )
    return payload


async def generate_journal_suggestions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
) -> SuggestionsResponse:
    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )

    suggestions: list[SuggestedJournal] = []
    current_from, current_to = _month_bounds(from_date)
    previous_from, previous_to = _month_bounds(_previous_month(from_date))

    current_net = await _gl_net_by_account(
        db,
        tenant_id=tenant_id,
        entity_ids=scope.entity_ids,
        from_dt=current_from,
        to_dt=current_to,
    )
    previous_net = await _gl_net_by_account(
        db,
        tenant_id=tenant_id,
        entity_ids=scope.entity_ids,
        from_dt=previous_from,
        to_dt=previous_to,
    )

    for account_code in sorted(previous_net.keys()):
        account_name, prev_amount = previous_net[account_code]
        if abs(prev_amount) < Decimal("1"):
            continue
        text = f"{account_code} {account_name}".upper()
        if "ACCRUAL" not in text and "PROVISION" not in text and "EXPENSE" not in text:
            continue
        curr_amount = current_net.get(account_code, ("", _ZERO))[1]
        if abs(curr_amount) >= Decimal("1"):
            continue

        amount = abs(prev_amount).quantize(Decimal("0.0001"))
        suggestions.append(
            SuggestedJournal(
                title=f"Missing accrual candidate for {account_code}",
                reason=(
                    f"Previous month net amount {prev_amount} for {account_code} "
                    "is missing in current month."
                ),
                suggested_date=to_date,
                lines=[
                    SuggestedJournalLine(
                        account_code=account_code,
                        entry_type="DEBIT",
                        amount=amount,
                        memo="Accrual catch-up expense",
                    ),
                    SuggestedJournalLine(
                        account_code="ACCRUALS_PAYABLE",
                        entry_type="CREDIT",
                        amount=amount,
                        memo="Accrual offset liability",
                    ),
                ],
                evidence={
                    "previous_month_amount": str(prev_amount),
                    "current_month_amount": str(curr_amount),
                    "source": "gl_entry_pattern",
                },
            )
        )

    variance = await compute_variance(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison="prev_month",
    )
    for row in variance.account_variances:
        pct = row.variance_percent
        if pct is None or abs(Decimal(str(pct))) < Decimal("50"):
            continue
        suggestions.append(
            SuggestedJournal(
                title=f"Review high variance account {row.account_code}",
                reason=(
                    f"Account {row.account_code} has {pct}% variance "
                    f"({row.current_value} vs {row.previous_value})."
                ),
                suggested_date=to_date,
                lines=[],
                evidence={
                    "account_code": row.account_code,
                    "variance_percent": str(pct),
                    "current_value": str(row.current_value),
                    "previous_value": str(row.previous_value),
                    "source": "analytics.variance",
                },
            )
        )

    recurring_result = (
        await db.execute(
            select(AccountingJVAggregate.reference, func.count(AccountingJVAggregate.id))
            .where(
                AccountingJVAggregate.tenant_id == tenant_id,
                AccountingJVAggregate.entity_id.in_(scope.entity_ids),
                AccountingJVAggregate.reference.is_not(None),
                AccountingJVAggregate.period_date >= (to_date - timedelta(days=120)),
                AccountingJVAggregate.status.in_(
                    [JVStatus.APPROVED, JVStatus.PUSHED, JVStatus.PUSH_FAILED]
                ),
            )
            .group_by(AccountingJVAggregate.reference)
            .order_by(AccountingJVAggregate.reference.asc())
        )
    ).all()
    for reference, count in recurring_result:
        if reference is None or count < 2:
            continue
        suggestions.append(
            SuggestedJournal(
                title=f"Recurring journal template candidate ({reference})",
                reason=(
                    f"Reference {reference} occurred {count} times in recent periods; "
                    "consider creating a controlled recurring journal template."
                ),
                suggested_date=to_date,
                lines=[],
                evidence={
                    "reference": reference,
                    "occurrence_count": int(count),
                    "source": "journal_history",
                },
            )
        )

    return SuggestionsResponse(
        rows=suggestions[:25],
        validation={
            "deterministic_sources": [
                "gl_entries",
                "analytics.variance",
                "accounting_jv_aggregates",
            ],
            "suggestions_count": min(len(suggestions), 25),
            "auto_posted": False,
        },
    )
