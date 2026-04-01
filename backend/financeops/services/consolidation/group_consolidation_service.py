from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationResult,
    ConsolidationRun,
    IntercompanyPair,
)
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.coa.models import CoaLedgerAccount, TenantCoaAccount
from financeops.modules.org_setup.models import OrgEntity, OrgGroup, OrgOwnership
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.consolidation.run_events import append_run_event, get_latest_run_event
from financeops.services.consolidation.run_store import get_run_or_raise

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class _EntityRow:
    org_entity_id: uuid.UUID
    cp_entity_id: uuid.UUID
    legal_name: str
    reporting_currency: str


@dataclass(frozen=True)
class _OwnershipEdge:
    parent_entity_id: uuid.UUID
    child_entity_id: uuid.UUID
    ownership_pct: Decimal
    consolidation_method: str


@dataclass(frozen=True)
class _GlAggregateRow:
    cp_entity_id: uuid.UUID
    account_code: str
    account_name: str
    debit_sum: Decimal
    credit_sum: Decimal
    bs_pl_flag: str | None
    asset_liability_class: str | None


@dataclass
class _AccountAggregate:
    account_code: str
    account_name: str
    debit_sum: Decimal
    credit_sum: Decimal
    balance: Decimal
    bs_pl_flag: str | None
    asset_liability_class: str | None


def _normalize(text: str | None) -> str:
    return (text or "").strip().upper()


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def _classify_pnl_bucket(*, account_code: str, account_name: str, bs_pl_flag: str | None) -> str:
    flag = _normalize(bs_pl_flag)
    text = f"{_normalize(account_code)} {_normalize(account_name)}"

    if flag in {"REVENUE", "INCOME"}:
        if "OTHER" in text:
            return "OTHER_INCOME"
        return "REVENUE"

    if flag in {"EXPENSE", "COST", "COGS"}:
        if any(token in text for token in ("COGS", "COST OF SALES", "DIRECT COST", "MATERIAL")):
            return "COST_OF_SALES"
        if any(token in text for token in ("INTEREST", "FINANCE", "BANK CHARGE", "OTHER EXPENSE")):
            return "OTHER_EXPENSE"
        return "OPERATING_EXPENSE"

    if "REVENUE" in text or "SALES" in text:
        return "REVENUE"
    if "INCOME" in text:
        return "OTHER_INCOME"
    return "OPERATING_EXPENSE"


def _classify_bs_bucket(
    *,
    bs_pl_flag: str | None,
    asset_liability_class: str | None,
    account_name: str,
) -> tuple[str | None, str | None]:
    flag = _normalize(bs_pl_flag)
    subtype = _normalize(asset_liability_class) or None

    if flag in {"ASSET", "LIABILITY", "EQUITY"}:
        return flag, subtype

    text = _normalize(account_name)
    if "ASSET" in text:
        return "ASSET", subtype
    if "LIABILITY" in text or "PAYABLE" in text:
        return "LIABILITY", subtype
    if "EQUITY" in text or "CAPITAL" in text:
        return "EQUITY", subtype
    return None, subtype


def _is_investment_account(code: str, name: str) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    return "INVEST" in text


def _is_equity_account(code: str, name: str, flag: str | None) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    return _normalize(flag) == "EQUITY" or "EQUITY" in text or "SHARE CAPITAL" in text


def _is_ic_receivable_account(code: str, name: str) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    return any(token in text for token in ("INTERCOMPANY", "DUE FROM", "RECEIVABLE"))


def _is_ic_payable_account(code: str, name: str) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    return any(token in text for token in ("INTERCOMPANY", "DUE TO", "PAYABLE"))


def _is_ic_revenue_account(code: str, name: str, flag: str | None) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    normalized_flag = _normalize(flag)
    return normalized_flag in {"REVENUE", "INCOME"} and (
        "INTERCOMPANY" in text or "IC" in text or "RELATED PARTY" in text
    )


def _is_ic_expense_account(code: str, name: str, flag: str | None) -> bool:
    text = f"{_normalize(code)} {_normalize(name)}"
    normalized_flag = _normalize(flag)
    return normalized_flag in {"EXPENSE", "COST", "COGS"} and (
        "INTERCOMPANY" in text or "IC" in text or "RELATED PARTY" in text
    )


async def _load_group_scope(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
    as_of_date: date,
) -> tuple[OrgGroup, list[_EntityRow], dict[uuid.UUID, _OwnershipEdge], dict[uuid.UUID, Decimal]]:
    group_result = await session.execute(
        select(OrgGroup).where(
            OrgGroup.id == org_group_id,
            OrgGroup.tenant_id == tenant_id,
        )
    )
    group = group_result.scalar_one_or_none()
    if group is None:
        raise NotFoundError("Organisation group not found")

    entities_result = await session.execute(
        select(OrgEntity).where(
            OrgEntity.tenant_id == tenant_id,
            OrgEntity.org_group_id == org_group_id,
            OrgEntity.is_active.is_(True),
            OrgEntity.cp_entity_id.is_not(None),
        )
    )
    entities_raw = list(entities_result.scalars().all())
    if not entities_raw:
        raise ValidationError("No active entities found under this group with cp_entity_id mapping.")

    entities = [
        _EntityRow(
            org_entity_id=item.id,
            cp_entity_id=uuid.UUID(str(item.cp_entity_id)),
            legal_name=item.legal_name,
            reporting_currency=item.reporting_currency,
        )
        for item in entities_raw
    ]

    entity_ids = [item.org_entity_id for item in entities]
    ownership_result = await session.execute(
        select(OrgOwnership).where(
            OrgOwnership.tenant_id == tenant_id,
            OrgOwnership.parent_entity_id.in_(entity_ids),
            OrgOwnership.child_entity_id.in_(entity_ids),
            OrgOwnership.effective_from <= as_of_date,
            or_(
                OrgOwnership.effective_to.is_(None),
                OrgOwnership.effective_to >= as_of_date,
            ),
        )
    )
    ownership_rows = list(ownership_result.scalars().all())

    ownership_by_child: dict[uuid.UUID, _OwnershipEdge] = {}
    for row in ownership_rows:
        candidate = _OwnershipEdge(
            parent_entity_id=row.parent_entity_id,
            child_entity_id=row.child_entity_id,
            ownership_pct=_to_decimal(row.ownership_pct),
            consolidation_method=str(row.consolidation_method),
        )
        existing = ownership_by_child.get(row.child_entity_id)
        if existing is None or _to_decimal(row.ownership_pct) >= existing.ownership_pct:
            ownership_by_child[row.child_entity_id] = candidate

    ownership_factor_cache: dict[uuid.UUID, Decimal] = {}

    def _resolve_factor(entity_id: uuid.UUID, seen: set[uuid.UUID]) -> Decimal:
        cached = ownership_factor_cache.get(entity_id)
        if cached is not None:
            return cached
        if entity_id in seen:
            ownership_factor_cache[entity_id] = _ZERO
            return _ZERO
        seen.add(entity_id)
        edge = ownership_by_child.get(entity_id)
        if edge is None:
            ownership_factor_cache[entity_id] = Decimal("1")
            return Decimal("1")
        if _normalize(edge.consolidation_method) != "FULL_CONSOLIDATION":
            ownership_factor_cache[entity_id] = _ZERO
            return _ZERO
        parent_factor = _resolve_factor(edge.parent_entity_id, seen)
        factor = (parent_factor * edge.ownership_pct) / _HUNDRED
        ownership_factor_cache[entity_id] = factor
        return factor

    ownership_factor: dict[uuid.UUID, Decimal] = {}
    for item in entities:
        ownership_factor[item.org_entity_id] = _resolve_factor(item.org_entity_id, set())

    return group, entities, ownership_by_child, ownership_factor


async def _fetch_gl_aggregates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    cp_entity_ids: list[uuid.UUID],
    as_of_date: date,
    from_date: date | None,
    to_date: date | None,
) -> list[_GlAggregateRow]:
    effective_upper_bound = _end_of_day(as_of_date)
    if to_date is not None:
        effective_upper_bound = min(effective_upper_bound, _end_of_day(to_date))

    stmt = (
        select(
            GlEntry.entity_id,
            GlEntry.account_code,
            GlEntry.account_name,
            func.coalesce(func.sum(GlEntry.debit_amount), _ZERO).label("debit_sum"),
            func.coalesce(func.sum(GlEntry.credit_amount), _ZERO).label("credit_sum"),
            CoaLedgerAccount.bs_pl_flag,
            CoaLedgerAccount.asset_liability_class,
        )
        .outerjoin(
            TenantCoaAccount,
            and_(
                TenantCoaAccount.tenant_id == tenant_id,
                TenantCoaAccount.account_code == GlEntry.account_code,
                TenantCoaAccount.is_active.is_(True),
            ),
        )
        .outerjoin(CoaLedgerAccount, CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id)
        .where(
            GlEntry.tenant_id == tenant_id,
            GlEntry.entity_id.in_(cp_entity_ids),
            GlEntry.created_at <= effective_upper_bound,
        )
        .group_by(
            GlEntry.entity_id,
            GlEntry.account_code,
            GlEntry.account_name,
            CoaLedgerAccount.bs_pl_flag,
            CoaLedgerAccount.asset_liability_class,
        )
    )

    if from_date is not None:
        stmt = stmt.where(GlEntry.created_at >= _start_of_day(from_date))

    result = await session.execute(stmt)
    rows: list[_GlAggregateRow] = []
    for item in result.all():
        if item.entity_id is None:
            continue
        rows.append(
            _GlAggregateRow(
                cp_entity_id=uuid.UUID(str(item.entity_id)),
                account_code=str(item.account_code),
                account_name=str(item.account_name),
                debit_sum=_to_decimal(item.debit_sum),
                credit_sum=_to_decimal(item.credit_sum),
                bs_pl_flag=item.bs_pl_flag,
                asset_liability_class=item.asset_liability_class,
            )
        )
    return rows


def _as_json_decimal(value: Decimal) -> str:
    return format(_quantize(value), "f")


def _build_eliminations(
    *,
    account_map: dict[str, _AccountAggregate],
    account_entity_exposure: dict[str, dict[uuid.UUID, Decimal]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eliminations: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    def _dominant_entity(account_code: str) -> uuid.UUID | None:
        candidates = account_entity_exposure.get(account_code) or {}
        if not candidates:
            return None
        return max(candidates.items(), key=lambda item: abs(item[1]))[0]

    def _pick_account(predicate) -> str | None:
        candidates = [row for row in account_map.values() if predicate(row)]
        if not candidates:
            return None
        return max(candidates, key=lambda row: abs(row.balance)).account_code

    def _append_elimination(
        *,
        elimination_type: str,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
    ) -> None:
        if amount <= _ZERO:
            return
        debit_row = account_map[debit_account]
        credit_row = account_map[credit_account]

        debit_row.debit_sum += amount
        debit_row.balance += amount
        credit_row.credit_sum += amount
        credit_row.balance -= amount

        entity_from = _dominant_entity(debit_account)
        entity_to = _dominant_entity(credit_account)
        eliminations.append(
            {
                "elimination_type": elimination_type,
                "debit_account": debit_account,
                "credit_account": credit_account,
                "amount": _quantize(amount),
                "entity_from": entity_from,
                "entity_to": entity_to,
            }
        )

    investment_code = _pick_account(lambda row: _is_investment_account(row.account_code, row.account_name))
    equity_code = _pick_account(
        lambda row: _is_equity_account(row.account_code, row.account_name, row.bs_pl_flag)
    )
    if investment_code and equity_code:
        amount = min(abs(account_map[investment_code].balance), abs(account_map[equity_code].balance))
        _append_elimination(
            elimination_type="INVESTMENT_VS_EQUITY",
            debit_account=equity_code,
            credit_account=investment_code,
            amount=amount,
        )

    receivable_code = _pick_account(
        lambda row: _is_ic_receivable_account(row.account_code, row.account_name)
    )
    payable_code = _pick_account(lambda row: _is_ic_payable_account(row.account_code, row.account_name))
    if receivable_code and payable_code:
        amount = min(abs(account_map[receivable_code].balance), abs(account_map[payable_code].balance))
        _append_elimination(
            elimination_type="INTERCOMPANY_RECEIVABLE_PAYABLE",
            debit_account=payable_code,
            credit_account=receivable_code,
            amount=amount,
        )

    revenue_code = _pick_account(
        lambda row: _is_ic_revenue_account(row.account_code, row.account_name, row.bs_pl_flag)
    )
    expense_code = _pick_account(
        lambda row: _is_ic_expense_account(row.account_code, row.account_name, row.bs_pl_flag)
    )
    if revenue_code and expense_code:
        amount = min(abs(account_map[revenue_code].balance), abs(account_map[expense_code].balance))
        _append_elimination(
            elimination_type="INTERCOMPANY_REVENUE_EXPENSE",
            debit_account=revenue_code,
            credit_account=expense_code,
            amount=amount,
        )

    totals_by_type: dict[str, Decimal] = {}
    for item in eliminations:
        totals_by_type[item["elimination_type"]] = totals_by_type.get(item["elimination_type"], _ZERO) + item["amount"]

    for elimination_type, amount in sorted(totals_by_type.items()):
        summary.append(
            {
                "elimination_type": elimination_type,
                "amount": _as_json_decimal(amount),
            }
        )

    return eliminations, summary


def _build_statement_payload(
    *,
    account_map: dict[str, _AccountAggregate],
) -> dict[str, Any]:
    rows = sorted(account_map.values(), key=lambda row: row.account_code)

    tb_rows: list[dict[str, str]] = []
    total_debit = _ZERO
    total_credit = _ZERO

    revenue = _ZERO
    cost_of_sales = _ZERO
    operating_expense = _ZERO
    other_income = _ZERO
    other_expense = _ZERO

    assets_rows: list[dict[str, str | None]] = []
    liabilities_rows: list[dict[str, str | None]] = []
    equity_rows: list[dict[str, str | None]] = []
    total_assets = _ZERO
    total_liabilities = _ZERO
    total_equity = _ZERO

    pnl_breakdown: list[dict[str, str]] = []

    for row in rows:
        debit = _quantize(row.debit_sum)
        credit = _quantize(row.credit_sum)
        balance = _quantize(row.balance)

        if debit == _ZERO and credit == _ZERO:
            continue

        total_debit += debit
        total_credit += credit

        tb_rows.append(
            {
                "account_code": row.account_code,
                "account_name": row.account_name,
                "debit_sum": _as_json_decimal(debit),
                "credit_sum": _as_json_decimal(credit),
                "balance": _as_json_decimal(balance),
            }
        )

        bucket = _classify_pnl_bucket(
            account_code=row.account_code,
            account_name=row.account_name,
            bs_pl_flag=row.bs_pl_flag,
        )
        pnl_amount = credit - debit if bucket in {"REVENUE", "OTHER_INCOME"} else debit - credit
        if pnl_amount != _ZERO:
            pnl_breakdown.append(
                {
                    "category": bucket,
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "amount": _as_json_decimal(pnl_amount),
                }
            )
            if bucket == "REVENUE":
                revenue += pnl_amount
            elif bucket == "COST_OF_SALES":
                cost_of_sales += pnl_amount
            elif bucket == "OPERATING_EXPENSE":
                operating_expense += pnl_amount
            elif bucket == "OTHER_INCOME":
                other_income += pnl_amount
            elif bucket == "OTHER_EXPENSE":
                other_expense += pnl_amount

        bs_bucket, subtype = _classify_bs_bucket(
            bs_pl_flag=row.bs_pl_flag,
            asset_liability_class=row.asset_liability_class,
            account_name=row.account_name,
        )
        if bs_bucket is None:
            continue

        if bs_bucket == "ASSET":
            amount = debit - credit
            total_assets += amount
            assets_rows.append(
                {
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "sub_type": subtype,
                    "amount": _as_json_decimal(amount),
                }
            )
        elif bs_bucket == "LIABILITY":
            amount = credit - debit
            total_liabilities += amount
            liabilities_rows.append(
                {
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "sub_type": subtype,
                    "amount": _as_json_decimal(amount),
                }
            )
        elif bs_bucket == "EQUITY":
            amount = credit - debit
            total_equity += amount
            equity_rows.append(
                {
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "sub_type": subtype,
                    "amount": _as_json_decimal(amount),
                }
            )

    gross_profit = revenue - cost_of_sales
    operating_profit = gross_profit - operating_expense
    net_profit = operating_profit + other_income - other_expense

    retained_earnings = net_profit
    total_equity += retained_earnings
    if retained_earnings != _ZERO:
        equity_rows.append(
            {
                "account_code": "RETAINED_EARNINGS",
                "account_name": "Retained Earnings (Derived)",
                "sub_type": None,
                "amount": _as_json_decimal(retained_earnings),
            }
        )

    liabilities_and_equity = total_liabilities + total_equity

    if abs(total_debit - total_credit) > _TOLERANCE:
        raise ValidationError(
            f"Consolidated trial balance is not balanced: debit={total_debit} credit={total_credit}"
        )
    if abs(total_assets - liabilities_and_equity) > _TOLERANCE:
        raise ValidationError(
            "Consolidated balance sheet integrity failed: assets must equal liabilities + equity."
        )

    return {
        "trial_balance": {
            "rows": tb_rows,
            "total_debit": _as_json_decimal(total_debit),
            "total_credit": _as_json_decimal(total_credit),
            "is_balanced": True,
        },
        "pnl": {
            "revenue": _as_json_decimal(revenue),
            "cost_of_sales": _as_json_decimal(cost_of_sales),
            "gross_profit": _as_json_decimal(gross_profit),
            "operating_expense": _as_json_decimal(operating_expense),
            "operating_profit": _as_json_decimal(operating_profit),
            "other_income": _as_json_decimal(other_income),
            "other_expense": _as_json_decimal(other_expense),
            "net_profit": _as_json_decimal(net_profit),
            "breakdown": pnl_breakdown,
        },
        "balance_sheet": {
            "assets": assets_rows,
            "liabilities": liabilities_rows,
            "equity": equity_rows,
            "totals": {
                "assets": _as_json_decimal(total_assets),
                "liabilities": _as_json_decimal(total_liabilities),
                "equity": _as_json_decimal(total_equity),
                "liabilities_and_equity": _as_json_decimal(liabilities_and_equity),
            },
            "is_balanced": True,
        },
    }


async def _compute_group_consolidation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
    as_of_date: date,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    group, entities, ownership_by_child, ownership_factor = await _load_group_scope(
        session,
        tenant_id=tenant_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
    )
    cp_to_org = {item.cp_entity_id: item for item in entities}
    gl_rows = await _fetch_gl_aggregates(
        session,
        tenant_id=tenant_id,
        cp_entity_ids=list(cp_to_org.keys()),
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )

    account_map: dict[str, _AccountAggregate] = {}
    entity_totals: dict[uuid.UUID, dict[str, Decimal]] = {
        item.org_entity_id: {"weighted_debit": _ZERO, "weighted_credit": _ZERO, "weighted_balance": _ZERO}
        for item in entities
    }
    entity_raw_equity: dict[uuid.UUID, Decimal] = {item.org_entity_id: _ZERO for item in entities}
    account_entity_exposure: dict[str, dict[uuid.UUID, Decimal]] = {}

    for row in gl_rows:
        entity = cp_to_org.get(row.cp_entity_id)
        if entity is None:
            continue
        factor = ownership_factor.get(entity.org_entity_id, _ZERO)
        if factor <= _ZERO:
            continue

        weighted_debit = _quantize(row.debit_sum * factor)
        weighted_credit = _quantize(row.credit_sum * factor)
        weighted_balance = _quantize(weighted_debit - weighted_credit)

        entity_totals[entity.org_entity_id]["weighted_debit"] += weighted_debit
        entity_totals[entity.org_entity_id]["weighted_credit"] += weighted_credit
        entity_totals[entity.org_entity_id]["weighted_balance"] += weighted_balance

        if _is_equity_account(row.account_code, row.account_name, row.bs_pl_flag):
            raw_balance = _quantize(row.debit_sum - row.credit_sum)
            edge = ownership_by_child.get(entity.org_entity_id)
            if edge is not None and edge.ownership_pct < _HUNDRED:
                entity_raw_equity[entity.org_entity_id] += abs(raw_balance) * ((_HUNDRED - edge.ownership_pct) / _HUNDRED)

        aggregate = account_map.get(row.account_code)
        if aggregate is None:
            aggregate = _AccountAggregate(
                account_code=row.account_code,
                account_name=row.account_name,
                debit_sum=_ZERO,
                credit_sum=_ZERO,
                balance=_ZERO,
                bs_pl_flag=row.bs_pl_flag,
                asset_liability_class=row.asset_liability_class,
            )
            account_map[row.account_code] = aggregate

        aggregate.debit_sum += weighted_debit
        aggregate.credit_sum += weighted_credit
        aggregate.balance += weighted_balance

        account_entity_exposure.setdefault(row.account_code, {})
        account_entity_exposure[row.account_code][entity.org_entity_id] = (
            account_entity_exposure[row.account_code].get(entity.org_entity_id, _ZERO) + weighted_balance
        )

    eliminations, elimination_summary = _build_eliminations(
        account_map=account_map,
        account_entity_exposure=account_entity_exposure,
    )

    elimination_debit_total = sum((item["amount"] for item in eliminations), start=_ZERO)
    elimination_credit_total = sum((item["amount"] for item in eliminations), start=_ZERO)
    if abs(elimination_debit_total - elimination_credit_total) > _TOLERANCE:
        raise ValidationError("Eliminations do not net to zero.")

    statements = _build_statement_payload(account_map=account_map)

    hierarchy_rows: list[dict[str, Any]] = []
    for item in entities:
        edge = ownership_by_child.get(item.org_entity_id)
        ownership_pct = edge.ownership_pct if edge is not None else _HUNDRED
        consolidation_method = edge.consolidation_method if edge is not None else "FULL_CONSOLIDATION"
        hierarchy_rows.append(
            {
                "org_entity_id": str(item.org_entity_id),
                "cp_entity_id": str(item.cp_entity_id),
                "legal_name": item.legal_name,
                "parent_entity_id": str(edge.parent_entity_id) if edge is not None else None,
                "ownership_pct": _as_json_decimal(ownership_pct),
                "ownership_factor": _as_json_decimal(ownership_factor[item.org_entity_id]),
                "consolidation_method": consolidation_method,
                "weighted_debit": _as_json_decimal(entity_totals[item.org_entity_id]["weighted_debit"]),
                "weighted_credit": _as_json_decimal(entity_totals[item.org_entity_id]["weighted_credit"]),
                "weighted_balance": _as_json_decimal(entity_totals[item.org_entity_id]["weighted_balance"]),
            }
        )

    root_entity = next((row for row in hierarchy_rows if row["parent_entity_id"] is None), None)
    minority_interest = _quantize(sum(entity_raw_equity.values(), start=_ZERO))

    total_eliminations = sum((_to_decimal(item["amount"]) for item in elimination_summary), start=_ZERO)

    summary = {
        "org_group_id": str(org_group_id),
        "group_name": group.group_name,
        "as_of_date": as_of_date.isoformat(),
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "reporting_currency": group.reporting_currency,
        "entity_count": len(entities),
        "elimination_count": len(eliminations),
        "total_eliminations": _as_json_decimal(total_eliminations),
        "minority_interest_placeholder": _as_json_decimal(minority_interest),
    }

    return {
        "summary": summary,
        "hierarchy": {
            "rows": hierarchy_rows,
            "root_cp_entity_id": root_entity["cp_entity_id"] if root_entity else None,
        },
        "statements": statements,
        "eliminations": eliminations,
        "elimination_summary": elimination_summary,
    }


async def get_group_consolidation_summary(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
    as_of_date: date,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    payload = await _compute_group_consolidation(
        session,
        tenant_id=tenant_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    return {
        "summary": payload["summary"],
        "hierarchy": payload["hierarchy"],
        "statements": payload["statements"],
        "elimination_summary": payload["elimination_summary"],
    }


async def run_group_consolidation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    initiated_by: uuid.UUID,
    org_group_id: uuid.UUID,
    as_of_date: date,
    from_date: date | None,
    to_date: date | None,
    correlation_id: str | None,
) -> dict[str, str]:
    payload = await _compute_group_consolidation(
        session,
        tenant_id=tenant_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )

    run_signature_payload = {
        "org_group_id": str(org_group_id),
        "as_of_date": as_of_date.isoformat(),
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "nonce": str(uuid.uuid4()),
    }
    request_signature = hashlib.sha256(
        json.dumps(run_signature_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    workflow_id = f"group-consolidation-{request_signature[:24]}"

    run = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": as_of_date.year,
            "period_month": as_of_date.month,
            "org_group_id": str(org_group_id),
            "request_signature": request_signature,
        },
        values={
            "period_year": as_of_date.year,
            "period_month": as_of_date.month,
            "entity_id": uuid.UUID(payload["hierarchy"]["root_cp_entity_id"]) if payload["hierarchy"]["root_cp_entity_id"] else None,
            "parent_currency": str(payload["summary"]["reporting_currency"]),
            "initiated_by": initiated_by,
            "request_signature": request_signature,
            "configuration_json": {
                "mode": "group_consolidation_v1",
                **run_signature_payload,
            },
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="consolidation.group.run.created",
            resource_type="consolidation_run",
            new_value={
                "run_id": "pending",
                "org_group_id": str(org_group_id),
                "as_of_date": as_of_date.isoformat(),
            },
        ),
    )

    await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run.id,
        user_id=initiated_by,
        event_type="accepted",
        idempotency_key="group-run-accepted",
        metadata_json={"workflow_id": workflow_id, "mode": "group_consolidation_v1"},
        correlation_id=correlation_id,
    )
    await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run.id,
        user_id=initiated_by,
        event_type="running",
        idempotency_key="group-run-running",
        metadata_json={"mode": "group_consolidation_v1"},
        correlation_id=correlation_id,
    )

    for row in payload["statements"]["trial_balance"]["rows"]:
        await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationResult,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run.id),
                "account_code": row["account_code"],
                "amount": row["balance"],
            },
            values={
                "run_id": run.id,
                "entity_id": uuid.UUID(payload["hierarchy"]["root_cp_entity_id"]) if payload["hierarchy"]["root_cp_entity_id"] else None,
                "consolidated_account_code": row["account_code"],
                "consolidated_amount_parent": _to_decimal(row["balance"]),
                "fx_impact_total": _ZERO,
                "correlation_id": correlation_id,
            },
        )

    for index, elimination in enumerate(payload["eliminations"], start=1):
        amount = _to_decimal(elimination["amount"])
        entity_from = elimination["entity_from"] or uuid.uuid4()
        entity_to = elimination["entity_to"] or uuid.uuid4()
        match_key_hash = hashlib.sha256(
            f"{run.id}:{index}:{elimination['elimination_type']}".encode("utf-8")
        ).hexdigest()
        pair = await AuditWriter.insert_financial_record(
            session,
            model_class=IntercompanyPair,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run.id),
                "match_key_hash": match_key_hash,
            },
            values={
                "run_id": run.id,
                "match_key_hash": match_key_hash,
                "entity_from": entity_from,
                "entity_to": entity_to,
                "account_code": elimination["credit_account"],
                "ic_reference": f"AUTO:{elimination['elimination_type']}:{index}",
                "amount_local_from": amount,
                "amount_local_to": amount,
                "amount_parent_from": amount,
                "amount_parent_to": amount,
                "expected_difference": _ZERO,
                "actual_difference": _ZERO,
                "fx_explained": _ZERO,
                "unexplained_difference": _ZERO,
                "classification": elimination["elimination_type"],
                "correlation_id": correlation_id,
            },
        )
        await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationElimination,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run.id),
                "pair_id": str(pair.id),
                "elimination_type": elimination["elimination_type"],
            },
            values={
                "run_id": run.id,
                "intercompany_pair_id": pair.id,
                "entity_from": entity_from,
                "entity_to": entity_to,
                "account_code": elimination["credit_account"],
                "classification_at_time": elimination["elimination_type"],
                "elimination_status": "APPLIED",
                "eliminated_amount_parent": amount,
                "fx_component_impact_parent": _ZERO,
                "residual_difference_parent": _ZERO,
                "rule_code": elimination["elimination_type"],
                "reason": (
                    f"Auto elimination: debit {elimination['debit_account']} "
                    f"credit {elimination['credit_account']}"
                ),
                "correlation_id": correlation_id,
            },
        )

    await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run.id,
        user_id=initiated_by,
        event_type="completed",
        idempotency_key="group-run-completed",
        metadata_json={
            "mode": "group_consolidation_v1",
            **payload,
        },
        correlation_id=correlation_id,
    )

    return {
        "run_id": str(run.id),
        "workflow_id": workflow_id,
        "status": "completed",
        "correlation_id": correlation_id or "",
    }


async def get_group_consolidation_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    event = await get_latest_run_event(session, tenant_id=tenant_id, run_id=run_id)

    metadata = event.metadata_json or {}
    summary = metadata.get("summary") if isinstance(metadata, dict) else None

    return {
        "run_id": str(run.id),
        "status": event.event_type,
        "event_seq": event.event_seq,
        "event_time": event.event_time,
        "workflow_id": run.workflow_id,
        "configuration": run.configuration_json,
        "summary": summary,
    }


async def get_group_consolidation_run_statements(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    event = await get_latest_run_event(session, tenant_id=tenant_id, run_id=run_id)

    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    if metadata and "statements" in metadata:
        return {
            "run_id": str(run_id),
            "status": event.event_type,
            "statements": metadata.get("statements"),
            "elimination_summary": metadata.get("elimination_summary", []),
            "eliminations": metadata.get("eliminations", []),
            "hierarchy": metadata.get("hierarchy"),
            "summary": metadata.get("summary"),
        }

    rows_result = await session.execute(
        select(ConsolidationResult)
        .where(
            ConsolidationResult.tenant_id == tenant_id,
            ConsolidationResult.run_id == run_id,
        )
        .order_by(ConsolidationResult.consolidated_account_code)
    )
    rows = list(rows_result.scalars().all())

    fallback_tb_rows = []
    total_debit = _ZERO
    total_credit = _ZERO
    for row in rows:
        balance = _to_decimal(row.consolidated_amount_parent)
        debit = balance if balance > _ZERO else _ZERO
        credit = -balance if balance < _ZERO else _ZERO
        total_debit += debit
        total_credit += credit
        fallback_tb_rows.append(
            {
                "account_code": row.consolidated_account_code,
                "account_name": row.consolidated_account_code,
                "debit_sum": _as_json_decimal(debit),
                "credit_sum": _as_json_decimal(credit),
                "balance": _as_json_decimal(balance),
            }
        )

    return {
        "run_id": str(run_id),
        "status": event.event_type,
        "statements": {
            "trial_balance": {
                "rows": fallback_tb_rows,
                "total_debit": _as_json_decimal(total_debit),
                "total_credit": _as_json_decimal(total_credit),
                "is_balanced": abs(total_debit - total_credit) <= _TOLERANCE,
            },
            "pnl": None,
            "balance_sheet": None,
        },
        "elimination_summary": [],
        "eliminations": [],
        "hierarchy": None,
        "summary": None,
    }
