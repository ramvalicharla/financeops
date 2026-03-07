from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry, ReconItem, TrialBalanceRow
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)


async def create_gl_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    account_code: str,
    account_name: str,
    debit_amount: Decimal,
    credit_amount: Decimal,
    uploaded_by: uuid.UUID,
    description: str | None = None,
    source_ref: str | None = None,
    currency: str = "USD",
) -> GlEntry:
    """Insert a single GL entry (INSERT ONLY)."""
    entry = await AuditWriter.insert_financial_record(
        session,
        model_class=GlEntry,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "debit_amount": str(debit_amount),
            "credit_amount": str(credit_amount),
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "debit_amount": debit_amount,
            "credit_amount": credit_amount,
            "description": description,
            "source_ref": source_ref,
            "currency": currency,
            "uploaded_by": uploaded_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=uploaded_by,
            action="recon.gl_entry.created",
            resource_type="gl_entry",
            resource_name=account_code,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
            },
        ),
    )
    return entry


async def create_tb_row(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    account_code: str,
    account_name: str,
    opening_balance: Decimal,
    period_debit: Decimal,
    period_credit: Decimal,
    closing_balance: Decimal,
    uploaded_by: uuid.UUID,
    currency: str = "USD",
) -> TrialBalanceRow:
    """Insert a single TB row (INSERT ONLY)."""
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=TrialBalanceRow,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "closing_balance": str(closing_balance),
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "entity_name": entity_name,
            "account_code": account_code,
            "account_name": account_name,
            "opening_balance": opening_balance,
            "period_debit": period_debit,
            "period_credit": period_credit,
            "closing_balance": closing_balance,
            "currency": currency,
            "uploaded_by": uploaded_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=uploaded_by,
            action="recon.tb_row.created",
            resource_type="trial_balance_row",
            resource_name=account_code,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
            },
        ),
    )
    return row


async def run_gl_tb_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    run_by: uuid.UUID,
) -> list[ReconItem]:
    """
    Compare GL entry sums vs TB closing balances for the period.
    Creates a ReconItem for every account with a non-zero difference.
    Returns list of ReconItems created (only breaks where difference != 0).
    """
    # Sum GL entries per account
    gl_result = await session.execute(
        select(
            GlEntry.account_code,
            GlEntry.account_name,
            func.sum(GlEntry.debit_amount - GlEntry.credit_amount).label("net"),
        )
        .where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.period_year == period_year,
            GlEntry.period_month == period_month,
            GlEntry.entity_name == entity_name,
        )
        .group_by(GlEntry.account_code, GlEntry.account_name)
    )
    gl_by_account: dict[str, tuple[str, Decimal]] = {
        row.account_code: (row.account_name, row.net or Decimal("0"))
        for row in gl_result
    }

    # Get TB closing balances per account
    tb_result = await session.execute(
        select(
            TrialBalanceRow.account_code,
            TrialBalanceRow.account_name,
            TrialBalanceRow.closing_balance,
        )
        .where(
            TrialBalanceRow.tenant_id == tenant_id,
            TrialBalanceRow.period_year == period_year,
            TrialBalanceRow.period_month == period_month,
            TrialBalanceRow.entity_name == entity_name,
        )
    )
    tb_by_account: dict[str, tuple[str, Decimal]] = {
        row.account_code: (row.account_name, row.closing_balance)
        for row in tb_result
    }

    # Find all accounts (union of GL and TB)
    all_accounts = set(gl_by_account.keys()) | set(tb_by_account.keys())

    items: list[ReconItem] = []
    for account_code in sorted(all_accounts):
        gl_account_name, gl_total = gl_by_account.get(account_code, ("", Decimal("0")))
        tb_account_name, tb_closing = tb_by_account.get(
            account_code, ("", Decimal("0"))
        )
        account_name = gl_account_name or tb_account_name

        difference = tb_closing - gl_total
        # Only create items where there's a break (difference != 0)
        if difference != Decimal("0"):
            item = await AuditWriter.insert_financial_record(
                session,
                model_class=ReconItem,
                tenant_id=tenant_id,
                record_data={
                    "tenant_id": str(tenant_id),
                    "period_year": period_year,
                    "period_month": period_month,
                    "entity_name": entity_name,
                    "account_code": account_code,
                    "gl_total": str(gl_total),
                    "tb_closing_balance": str(tb_closing),
                    "difference": str(difference),
                },
                values={
                    "period_year": period_year,
                    "period_month": period_month,
                    "entity_name": entity_name,
                    "account_code": account_code,
                    "account_name": account_name,
                    "gl_total": gl_total,
                    "tb_closing_balance": tb_closing,
                    "difference": difference,
                    "status": "open",
                    "recon_type": "gl_tb",
                    "run_by": run_by,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=run_by,
                    action="recon.break.created",
                    resource_type="recon_item",
                    resource_name=account_code,
                    new_value={
                        "entity_name": entity_name,
                        "period_year": period_year,
                        "period_month": period_month,
                    },
                ),
            )
            items.append(item)

    log.info(
        "Reconciliation run: tenant=%s entity=%s period=%d/%d breaks=%d",
        str(tenant_id)[:8], entity_name, period_year, period_month, len(items),
    )
    return items


async def list_recon_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ReconItem]:
    stmt = select(ReconItem).where(ReconItem.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(ReconItem.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(ReconItem.period_month == period_month)
    if entity_name:
        stmt = stmt.where(ReconItem.entity_name == entity_name)
    if status:
        stmt = stmt.where(ReconItem.status == status)
    stmt = stmt.order_by(desc(ReconItem.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_gl_entries(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[GlEntry]:
    stmt = select(GlEntry).where(GlEntry.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(GlEntry.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(GlEntry.period_month == period_month)
    if entity_name:
        stmt = stmt.where(GlEntry.entity_name == entity_name)
    stmt = stmt.order_by(desc(GlEntry.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_tb_rows(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TrialBalanceRow]:
    stmt = select(TrialBalanceRow).where(TrialBalanceRow.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(TrialBalanceRow.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(TrialBalanceRow.period_month == period_month)
    if entity_name:
        stmt = stmt.where(TrialBalanceRow.entity_name == entity_name)
    stmt = stmt.order_by(TrialBalanceRow.account_code).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())
