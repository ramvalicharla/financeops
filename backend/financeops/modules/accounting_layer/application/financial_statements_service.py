from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.accounting_layer.domain.schemas import (
    BalanceSheetItem,
    BalanceSheetResponse,
    BalanceSheetTotals,
    CashFlowBreakdownRow,
    CashFlowResponse,
    PnLBreakdownRow,
    PnLResponse,
)
from financeops.modules.coa.models import CoaLedgerAccount, TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity

_ZERO = Decimal("0")
_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class _AccountAggregate:
    account_code: str
    account_name: str
    debit_sum: Decimal
    credit_sum: Decimal
    bs_pl_flag: str | None
    asset_liability_class: str | None
    cash_flow_tag: str | None
    normal_balance: str | None


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _normalize(value: str | None) -> str:
    return (value or "").strip().upper()


def _signed_amount_for_bucket(row: _AccountAggregate, bucket: str) -> Decimal:
    if bucket in {"REVENUE", "OTHER_INCOME"}:
        return row.credit_sum - row.debit_sum
    return row.debit_sum - row.credit_sum


def _net_profit_from_rows(rows: list[_AccountAggregate]) -> Decimal:
    revenue = _ZERO
    cost_of_sales = _ZERO
    operating_expense = _ZERO
    other_income = _ZERO
    other_expense = _ZERO

    for row in rows:
        bucket = _classify_pnl_bucket(row)
        amount = _signed_amount_for_bucket(row, bucket)
        if bucket == "REVENUE":
            revenue += amount
        elif bucket == "COST_OF_SALES":
            cost_of_sales += amount
        elif bucket == "OPERATING_EXPENSE":
            operating_expense += amount
        elif bucket == "OTHER_INCOME":
            other_income += amount
        elif bucket == "OTHER_EXPENSE":
            other_expense += amount

    gross_profit = revenue - cost_of_sales
    operating_profit = gross_profit - operating_expense
    return operating_profit + other_income - other_expense


def _classify_pnl_bucket(row: _AccountAggregate) -> str:
    flag = _normalize(row.bs_pl_flag)
    code = _normalize(row.account_code)
    name = _normalize(row.account_name)
    text = f"{code} {name}"

    if flag in {"REVENUE", "INCOME"}:
        if "OTHER" in text:
            return "OTHER_INCOME"
        return "REVENUE"

    if flag in {"EXPENSE", "COST", "COGS"}:
        if any(token in text for token in ("COGS", "COST OF SALES", "COST_OF_SALES", "DIRECT COST", "MATERIAL")):
            return "COST_OF_SALES"
        if any(token in text for token in ("INTEREST", "FINANCE", "BANK CHARGE", "OTHER EXPENSE")):
            return "OTHER_EXPENSE"
        return "OPERATING_EXPENSE"

    if row.credit_sum >= row.debit_sum:
        return "OTHER_INCOME"
    return "OPERATING_EXPENSE"


def _classify_balance_sheet_bucket(row: _AccountAggregate) -> tuple[str, str | None]:
    flag = _normalize(row.bs_pl_flag)
    subtype = _normalize(row.asset_liability_class) or None

    if flag == "ASSET":
        return "ASSET", subtype
    if flag == "LIABILITY":
        return "LIABILITY", subtype
    if flag in {"EQUITY", "OCI"}:
        return "EQUITY", subtype

    if _normalize(row.normal_balance) == "CREDIT":
        return "LIABILITY", subtype
    return "ASSET", subtype


def _balance_amount(row: _AccountAggregate, bucket: str) -> Decimal:
    if bucket == "ASSET":
        return row.debit_sum - row.credit_sum
    return row.credit_sum - row.debit_sum


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


async def _fetch_account_aggregates(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime,
) -> list[_AccountAggregate]:
    stmt = (
        select(
            GlEntry.account_code,
            GlEntry.account_name,
            func.coalesce(func.sum(GlEntry.debit_amount), _ZERO).label("debit_sum"),
            func.coalesce(func.sum(GlEntry.credit_amount), _ZERO).label("credit_sum"),
            CoaLedgerAccount.bs_pl_flag,
            CoaLedgerAccount.asset_liability_class,
            CoaLedgerAccount.cash_flow_tag,
            CoaLedgerAccount.normal_balance,
        )
        .outerjoin(
            TenantCoaAccount,
            and_(
                TenantCoaAccount.tenant_id == tenant_id,
                TenantCoaAccount.account_code == GlEntry.account_code,
                TenantCoaAccount.is_active.is_(True),
            ),
        )
        .outerjoin(
            CoaLedgerAccount,
            CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id,
        )
        .where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.entity_id == org_entity_id,
            GlEntry.created_at <= to_dt,
        )
        .group_by(
            GlEntry.account_code,
            GlEntry.account_name,
            CoaLedgerAccount.bs_pl_flag,
            CoaLedgerAccount.asset_liability_class,
            CoaLedgerAccount.cash_flow_tag,
            CoaLedgerAccount.normal_balance,
        )
        .order_by(GlEntry.account_code.asc())
    )
    if from_dt is not None:
        stmt = stmt.where(GlEntry.created_at >= from_dt)

    result = await db.execute(stmt)
    rows: list[_AccountAggregate] = []
    for item in result.all():
        rows.append(
            _AccountAggregate(
                account_code=item.account_code,
                account_name=item.account_name,
                debit_sum=Decimal(str(item.debit_sum or "0")),
                credit_sum=Decimal(str(item.credit_sum or "0")),
                bs_pl_flag=item.bs_pl_flag,
                asset_liability_class=item.asset_liability_class,
                cash_flow_tag=item.cash_flow_tag,
                normal_balance=item.normal_balance,
            )
        )
    return rows


async def get_profit_and_loss(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> PnLResponse:
    if from_date > to_date:
        raise ValidationError("from_date cannot be after to_date.")

    await _assert_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
    )

    rows = await _fetch_account_aggregates(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_dt=_start_of_day(from_date),
        to_dt=_end_of_day(to_date),
    )

    breakdown: list[PnLBreakdownRow] = []
    revenue = _ZERO
    cost_of_sales = _ZERO
    operating_expense = _ZERO
    other_income = _ZERO
    other_expense = _ZERO

    for row in rows:
        bucket = _classify_pnl_bucket(row)
        amount = _signed_amount_for_bucket(row, bucket)
        if amount == _ZERO:
            continue
        breakdown.append(
            PnLBreakdownRow(
                category=bucket,
                account_code=row.account_code,
                account_name=row.account_name,
                amount=amount,
                debit_sum=row.debit_sum,
                credit_sum=row.credit_sum,
            )
        )
        if bucket == "REVENUE":
            revenue += amount
        elif bucket == "COST_OF_SALES":
            cost_of_sales += amount
        elif bucket == "OPERATING_EXPENSE":
            operating_expense += amount
        elif bucket == "OTHER_INCOME":
            other_income += amount
        elif bucket == "OTHER_EXPENSE":
            other_expense += amount

    gross_profit = revenue - cost_of_sales
    operating_profit = gross_profit - operating_expense
    net_profit = operating_profit + other_income - other_expense
    control_net = _ZERO
    for row in rows:
        bucket = _classify_pnl_bucket(row)
        amount = _signed_amount_for_bucket(row, bucket)
        if bucket in {"REVENUE", "OTHER_INCOME"}:
            control_net += amount
        else:
            control_net -= amount
    if abs(net_profit - control_net) > _TOLERANCE:
        raise ValidationError("P&L integrity failed: calculated net profit mismatch.")

    return PnLResponse(
        org_entity_id=org_entity_id,
        from_date=from_date,
        to_date=to_date,
        revenue=revenue,
        cost_of_sales=cost_of_sales,
        gross_profit=gross_profit,
        operating_expense=operating_expense,
        operating_profit=operating_profit,
        other_income=other_income,
        other_expense=other_expense,
        net_profit=net_profit,
        breakdown=breakdown,
    )


async def get_balance_sheet(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    as_of_date: date,
) -> BalanceSheetResponse:
    await _assert_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
    )

    rows = await _fetch_account_aggregates(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_dt=None,
        to_dt=_end_of_day(as_of_date),
    )

    assets: list[BalanceSheetItem] = []
    liabilities: list[BalanceSheetItem] = []
    equity: list[BalanceSheetItem] = []
    total_assets = _ZERO
    total_liabilities = _ZERO
    total_equity = _ZERO

    retained_earnings = _net_profit_from_rows(rows)

    for row in rows:
        bucket, subtype = _classify_balance_sheet_bucket(row)
        amount = _balance_amount(row, bucket)
        if amount == _ZERO:
            continue

        item = BalanceSheetItem(
            account_code=row.account_code,
            account_name=row.account_name,
            account_type=bucket,
            sub_type=subtype,
            amount=amount,
        )
        if bucket == "ASSET":
            assets.append(item)
            total_assets += amount
        elif bucket == "LIABILITY":
            liabilities.append(item)
            total_liabilities += amount
        else:
            equity.append(item)
            total_equity += amount

    if retained_earnings != _ZERO:
        equity.append(
            BalanceSheetItem(
                account_code="RETAINED_EARNINGS",
                account_name="Retained Earnings (Derived)",
                account_type="EQUITY",
                sub_type=None,
                amount=retained_earnings,
            )
        )
        total_equity += retained_earnings

    liabilities_and_equity = total_liabilities + total_equity
    if abs(total_assets - liabilities_and_equity) > _TOLERANCE:
        raise ValidationError(
            "Balance sheet integrity failed: assets must equal liabilities + equity."
        )

    return BalanceSheetResponse(
        org_entity_id=org_entity_id,
        as_of_date=as_of_date,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        retained_earnings=retained_earnings,
        totals=BalanceSheetTotals(
            assets=total_assets,
            liabilities=total_liabilities,
            equity=total_equity,
            liabilities_and_equity=liabilities_and_equity,
        ),
    )


async def get_cash_flow_statement(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> CashFlowResponse:
    if from_date > to_date:
        raise ValidationError("from_date cannot be after to_date.")

    await _assert_entity_for_tenant(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
    )

    period_rows = await _fetch_account_aggregates(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_dt=_start_of_day(from_date),
        to_dt=_end_of_day(to_date),
    )

    pnl = await get_profit_and_loss(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_date=from_date,
        to_date=to_date,
    )
    net_profit = pnl.net_profit

    non_cash_adjustments = _ZERO
    for row in period_rows:
        text = f"{_normalize(row.account_code)} {_normalize(row.account_name)}"
        if "DEPRECIATION" in text or "AMORT" in text or _normalize(row.cash_flow_tag) == "EXCLUDED":
            pnl_bucket = _classify_pnl_bucket(row)
            if pnl_bucket in {"OPERATING_EXPENSE", "OTHER_EXPENSE", "COST_OF_SALES"}:
                non_cash_adjustments += _signed_amount_for_bucket(row, pnl_bucket)

    opening_rows = await _fetch_account_aggregates(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_dt=None,
        to_dt=_end_of_day(from_date - timedelta(days=1)),
    )
    closing_rows = await _fetch_account_aggregates(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        from_dt=None,
        to_dt=_end_of_day(to_date),
    )
    opening_map = {row.account_code: row for row in opening_rows}
    closing_map = {row.account_code: row for row in closing_rows}

    working_capital_changes = _ZERO
    for account_code, close_row in closing_map.items():
        bucket, subtype = _classify_balance_sheet_bucket(close_row)
        if bucket not in {"ASSET", "LIABILITY"} or subtype != "CURRENT":
            continue

        open_row = opening_map.get(account_code)
        open_amount = _balance_amount(open_row, bucket) if open_row else _ZERO
        close_amount = _balance_amount(close_row, bucket)
        delta = close_amount - open_amount
        if bucket == "ASSET":
            working_capital_changes -= delta
        else:
            working_capital_changes += delta

    operating_cash_flow = net_profit + non_cash_adjustments + working_capital_changes

    investing_cash_flow = _ZERO
    financing_cash_flow = _ZERO
    for row in period_rows:
        tag = _normalize(row.cash_flow_tag)
        movement = row.credit_sum - row.debit_sum
        if tag == "INVESTING":
            investing_cash_flow += movement
        elif tag == "FINANCING":
            financing_cash_flow += movement

    net_cash_flow = operating_cash_flow + investing_cash_flow + financing_cash_flow

    cash_delta = _ZERO
    for row in period_rows:
        text = f"{_normalize(row.account_code)} {_normalize(row.account_name)}"
        if "CASH" in text or "BANK" in text:
            cash_delta += row.debit_sum - row.credit_sum
    if abs(cash_delta - net_cash_flow) > _TOLERANCE and cash_delta != _ZERO:
        raise ValidationError(
            "Cash flow integrity failed: calculated net cash flow does not match cash account movement."
        )

    breakdown = [
        CashFlowBreakdownRow(category="NET_PROFIT", amount=net_profit),
        CashFlowBreakdownRow(category="NON_CASH_ADJUSTMENTS", amount=non_cash_adjustments),
        CashFlowBreakdownRow(category="WORKING_CAPITAL_CHANGES", amount=working_capital_changes),
        CashFlowBreakdownRow(category="OPERATING", amount=operating_cash_flow),
        CashFlowBreakdownRow(category="INVESTING", amount=investing_cash_flow),
        CashFlowBreakdownRow(category="FINANCING", amount=financing_cash_flow),
    ]

    return CashFlowResponse(
        org_entity_id=org_entity_id,
        from_date=from_date,
        to_date=to_date,
        net_profit=net_profit,
        non_cash_adjustments=non_cash_adjustments,
        working_capital_changes=working_capital_changes,
        operating_cash_flow=operating_cash_flow,
        investing_cash_flow=investing_cash_flow,
        financing_cash_flow=financing_cash_flow,
        net_cash_flow=net_cash_flow,
        breakdown=breakdown,
    )
