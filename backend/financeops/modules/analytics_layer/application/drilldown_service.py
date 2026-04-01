from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.application.financial_statements_service import (
    get_balance_sheet,
    get_profit_and_loss,
)
from financeops.modules.analytics_layer.application.common import resolve_scope
from financeops.modules.analytics_layer.schemas import (
    DrilldownAccountRow,
    DrilldownGlRow,
    DrilldownJournalRow,
    DrilldownResponse,
)

_ZERO = Decimal("0")


def _metric_group(metric_name: str) -> str:
    normalized = metric_name.strip().lower()
    if normalized in {
        "revenue",
        "gross_profit",
        "ebitda",
        "net_profit",
        "operating_margin",
        "net_margin",
        "interest_coverage",
    }:
        return "pnl"
    if normalized in {"current_ratio", "quick_ratio", "debt_equity", "roe", "roa", "asset_turnover"}:
        return "bs"
    return "all"


async def get_metric_drilldown(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metric_name: str,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    as_of_date: date,
) -> DrilldownResponse:
    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )

    account_rows: dict[str, DrilldownAccountRow] = {}
    mode = _metric_group(metric_name)
    for entity_id in scope.entity_ids:
        if mode in {"pnl", "all"}:
            pnl = await get_profit_and_loss(
                db,
                tenant_id=tenant_id,
                org_entity_id=entity_id,
                from_date=scope.from_date,
                to_date=scope.to_date,
            )
            for row in pnl.breakdown:
                item = account_rows.get(row.account_code)
                if item is None:
                    account_rows[row.account_code] = DrilldownAccountRow(
                        account_code=row.account_code,
                        account_name=row.account_name,
                        amount=row.amount,
                    )
                else:
                    item.amount += row.amount

        if mode in {"bs", "all"}:
            bs = await get_balance_sheet(
                db,
                tenant_id=tenant_id,
                org_entity_id=entity_id,
                as_of_date=scope.as_of_date,
            )
            for item in [*bs.assets, *bs.liabilities, *bs.equity]:
                existing = account_rows.get(item.account_code)
                if existing is None:
                    account_rows[item.account_code] = DrilldownAccountRow(
                        account_code=item.account_code,
                        account_name=item.account_name,
                        amount=item.amount,
                    )
                else:
                    existing.amount += item.amount

    codes = sorted(account_rows.keys())
    gl_entries: list[DrilldownGlRow] = []
    journals: list[DrilldownJournalRow] = []
    if codes:
        from_dt = datetime.combine(scope.from_date, time.min, tzinfo=timezone.utc)
        to_dt = datetime.combine(scope.to_date, time.max, tzinfo=timezone.utc)
        gl_rows = (
            await db.execute(
                select(GlEntry).where(
                    and_(
                        GlEntry.tenant_id == tenant_id,
                        GlEntry.entity_id.in_(scope.entity_ids),
                        GlEntry.account_code.in_(codes),
                        GlEntry.created_at >= from_dt,
                        GlEntry.created_at <= to_dt,
                    )
                ).order_by(GlEntry.created_at.desc())
                .limit(500)
            )
        ).scalars().all()

        refs: set[str] = set()
        for row in gl_rows:
            gl_entries.append(
                DrilldownGlRow(
                    gl_entry_id=row.id,
                    account_code=row.account_code,
                    account_name=row.account_name,
                    debit_amount=row.debit_amount,
                    credit_amount=row.credit_amount,
                    source_ref=row.source_ref,
                    created_at=row.created_at,
                )
            )
            if row.source_ref:
                refs.add(row.source_ref)

        if refs:
            journal_rows = (
                await db.execute(
                    select(AccountingJVAggregate).where(
                        AccountingJVAggregate.tenant_id == tenant_id,
                        AccountingJVAggregate.jv_number.in_(sorted(refs)),
                    ).order_by(AccountingJVAggregate.period_date.desc())
                    .limit(200)
                )
            ).scalars().all()
            for row in journal_rows:
                journals.append(
                    DrilldownJournalRow(
                        journal_id=row.id,
                        journal_number=row.jv_number,
                        journal_date=row.period_date,
                        status=row.status,
                        source_ref=row.external_reference_id or row.reference,
                    )
                )

    return DrilldownResponse(
        metric_name=metric_name,
        accounts=list(account_rows.values()),
        journals=journals,
        gl_entries=gl_entries,
        lineage={
            "mode": mode,
            "entity_ids": [str(item) for item in scope.entity_ids],
            "from_date": str(scope.from_date),
            "to_date": str(scope.to_date),
            "as_of_date": str(scope.as_of_date),
        },
    )

