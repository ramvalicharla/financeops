from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry
from financeops.modules.coa.models import CoaAccountGroup, CoaAccountSubgroup, CoaLedgerAccount, TenantCoaAccount

_ZERO = Decimal("0")


def _periods_for_window(period: str, months: int | None = None) -> list[tuple[int, int]]:
    year_text, month_text = str(period).split("-", 1)
    year = int(year_text)
    month = int(month_text)
    span = max(1, int(months or 1))

    values: list[tuple[int, int]] = []
    current_year = year
    current_month = month
    for _ in range(span):
        values.append((current_year, current_month))
        current_month -= 1
        if current_month == 0:
            current_month = 12
            current_year -= 1
    return values


def _name_or_code_match_clauses(*tokens: str):
    clauses = []
    for token in tokens:
        pattern = f"%{token.upper()}%"
        clauses.extend(
            [
                func.upper(func.coalesce(GlEntry.account_name, "")).like(pattern),
                func.upper(func.coalesce(GlEntry.account_code, "")).like(pattern),
                func.upper(func.coalesce(TenantCoaAccount.display_name, "")).like(pattern),
                func.upper(func.coalesce(CoaLedgerAccount.name, "")).like(pattern),
                func.upper(func.coalesce(CoaLedgerAccount.code, "")).like(pattern),
            ]
        )
    return or_(*clauses)


def _logical_group_filter(account_group: str):
    group_key = str(account_group or "").strip().upper()
    if group_key == "ACCOUNTS_RECEIVABLE":
        return or_(
            _name_or_code_match_clauses("RECEIVABLE", "TRADE RECEIVABLE"),
            and_(
                CoaAccountGroup.code == "CURRENT_ASSETS",
                _name_or_code_match_clauses("RECEIVABLE"),
            ),
        )
    if group_key == "ACCOUNTS_PAYABLE":
        return or_(
            _name_or_code_match_clauses("PAYABLE", "TRADE PAYABLE"),
            and_(
                CoaAccountGroup.code == "CURRENT_LIABILITIES",
                _name_or_code_match_clauses("PAYABLE"),
            ),
        )
    if group_key == "INVENTORY":
        return or_(
            _name_or_code_match_clauses("INVENT", "STOCK"),
            and_(
                CoaAccountGroup.code == "CURRENT_ASSETS",
                _name_or_code_match_clauses("INVENT"),
            ),
        )
    if group_key == "CURRENT_ASSETS":
        return or_(
            CoaAccountGroup.code == "CURRENT_ASSETS",
            and_(
                func.upper(func.coalesce(CoaLedgerAccount.bs_pl_flag, "")) == "ASSET",
                func.upper(func.coalesce(CoaLedgerAccount.asset_liability_class, "")) == "CURRENT",
            ),
            _name_or_code_match_clauses("RECEIVABLE", "INVENT", "CASH", "PREPAID", "CURRENT ASSET"),
        )
    if group_key == "CURRENT_LIABILITIES":
        return or_(
            CoaAccountGroup.code == "CURRENT_LIABILITIES",
            and_(
                func.upper(func.coalesce(CoaLedgerAccount.bs_pl_flag, "")) == "LIABILITY",
                func.upper(func.coalesce(CoaLedgerAccount.asset_liability_class, "")) == "CURRENT",
            ),
            _name_or_code_match_clauses("PAYABLE", "ACCRUED", "CURRENT LIAB", "SHORT TERM"),
        )
    if group_key == "REVENUE":
        return or_(
            func.upper(func.coalesce(CoaLedgerAccount.bs_pl_flag, "")) == "REVENUE",
            _name_or_code_match_clauses("REVENUE", "OTHER INCOME", "OPERATING INCOME"),
        )
    if group_key == "COST_OF_SALES":
        return or_(
            _name_or_code_match_clauses("COGS", "COST OF SALES", "DIRECT COST", "MATERIAL"),
            and_(
                func.upper(func.coalesce(CoaLedgerAccount.bs_pl_flag, "")) == "EXPENSE",
                _name_or_code_match_clauses("COST"),
            ),
        )
    raise ValueError(f"Unsupported account group: {account_group}")


def _signed_amount(account_group: str, debit_sum: Decimal, credit_sum: Decimal) -> Decimal:
    group_key = str(account_group or "").strip().upper()
    if group_key in {"ACCOUNTS_PAYABLE", "CURRENT_LIABILITIES", "REVENUE"}:
        return Decimal(str(credit_sum)) - Decimal(str(debit_sum))
    return Decimal(str(debit_sum)) - Decimal(str(credit_sum))


class AccountingLayerRepository:
    async def has_gl_activity(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
        *,
        period: str,
        entity_id: uuid.UUID | None = None,
        months: int | None = None,
    ) -> bool:
        periods = _periods_for_window(period, months=months)
        stmt = select(func.count()).select_from(GlEntry).where(
            GlEntry.tenant_id == tenant_id,
            tuple_(GlEntry.period_year, GlEntry.period_month).in_(periods),
        )
        if entity_id is not None:
            stmt = stmt.where(GlEntry.entity_id == entity_id)
        return bool((await db.execute(stmt)).scalar_one() or 0)

    async def get_balance_by_account_group(
        self,
        tenant_id: uuid.UUID,
        account_group: str,
        db: AsyncSession,
        *,
        period: str,
        entity_id: uuid.UUID | None = None,
        months: int | None = None,
    ) -> Decimal:
        periods = _periods_for_window(period, months=months)
        stmt = (
            select(
                func.coalesce(func.sum(GlEntry.debit_amount), _ZERO).label("debit_sum"),
                func.coalesce(func.sum(GlEntry.credit_amount), _ZERO).label("credit_sum"),
            )
            .select_from(GlEntry)
            .outerjoin(
                TenantCoaAccount,
                and_(
                    TenantCoaAccount.tenant_id == tenant_id,
                    TenantCoaAccount.account_code == GlEntry.account_code,
                    TenantCoaAccount.is_active.is_(True),
                ),
            )
            .outerjoin(CoaLedgerAccount, CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id)
            .outerjoin(CoaAccountSubgroup, CoaAccountSubgroup.id == TenantCoaAccount.parent_subgroup_id)
            .outerjoin(CoaAccountGroup, CoaAccountGroup.id == CoaAccountSubgroup.account_group_id)
            .where(
                GlEntry.tenant_id == tenant_id,
                tuple_(GlEntry.period_year, GlEntry.period_month).in_(periods),
                _logical_group_filter(account_group),
            )
        )
        if entity_id is not None:
            stmt = stmt.where(GlEntry.entity_id == entity_id)

        row = (await db.execute(stmt)).one()
        return _signed_amount(account_group, Decimal(str(row.debit_sum or "0")), Decimal(str(row.credit_sum or "0")))


__all__ = ["AccountingLayerRepository"]
