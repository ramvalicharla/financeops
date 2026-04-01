from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.accounting_jv import AccountingJVAggregate, AccountingJVLine, EntryType, JVStatus
from financeops.db.models.fx_ias21 import AccountingFxRevaluationLine, AccountingFxRevaluationRun
from financeops.modules.accounting_layer.application.journal_service import approve_journal, post_journal
from financeops.modules.accounting_layer.application.governance_service import (
    assert_period_allows_revaluation,
    record_governance_event,
)
from financeops.modules.accounting_layer.application.jv_service import create_jv
from financeops.modules.coa.models import CoaLedgerAccount, TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditWriter
from financeops.services.fx.ias21_math import compute_revaluation_delta
from financeops.services.fx.rate_master_service import get_required_latest_fx_rate

_ZERO = Decimal("0")
_GAIN_LOSS_ACCOUNT_CODE = "FX_GAIN_LOSS"
_GAIN_LOSS_ACCOUNT_NAME = "Foreign Exchange Gain/Loss"


@dataclass(frozen=True)
class _Exposure:
    account_code: str
    account_name: str
    transaction_currency: str
    functional_currency: str
    foreign_balance: Decimal
    historical_base_balance: Decimal


def _is_monetary_fallback(code: str, name: str) -> bool:
    text = f"{code} {name}".upper()
    return any(token in text for token in ("CASH", "BANK", "RECEIVABLE", "PAYABLE", "DUE FROM", "DUE TO"))


async def _get_entity_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> CpEntity:
    stmt = select(CpEntity).where(
        CpEntity.id == entity_id,
        CpEntity.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise ValidationError("Entity does not belong to tenant.")
    return entity


async def _load_monetary_exposures(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    as_of_date: date,
    functional_currency: str,
) -> list[_Exposure]:
    signed_foreign = case(
        (AccountingJVLine.entry_type == EntryType.DEBIT, AccountingJVLine.amount),
        else_=-AccountingJVLine.amount,
    )
    signed_base = case(
        (
            AccountingJVLine.entry_type == EntryType.DEBIT,
            func.coalesce(AccountingJVLine.base_amount, AccountingJVLine.amount_inr, AccountingJVLine.amount),
        ),
        else_=-func.coalesce(AccountingJVLine.base_amount, AccountingJVLine.amount_inr, AccountingJVLine.amount),
    )
    stmt = (
        select(
            AccountingJVLine.account_code,
            func.coalesce(AccountingJVLine.account_name, AccountingJVLine.account_code).label("account_name"),
            func.coalesce(
                AccountingJVLine.transaction_currency,
                AccountingJVLine.currency,
                functional_currency,
            ).label("transaction_currency"),
            func.coalesce(AccountingJVLine.functional_currency, functional_currency).label("functional_currency"),
            func.coalesce(func.sum(signed_foreign), _ZERO).label("foreign_balance"),
            func.coalesce(func.sum(signed_base), _ZERO).label("historical_base_balance"),
            func.bool_or(func.coalesce(CoaLedgerAccount.is_monetary, False)).label("is_monetary"),
        )
        .join(
            AccountingJVAggregate,
            and_(
                AccountingJVAggregate.id == AccountingJVLine.jv_id,
                AccountingJVAggregate.tenant_id == tenant_id,
            ),
        )
        .outerjoin(
            TenantCoaAccount,
            and_(
                TenantCoaAccount.tenant_id == tenant_id,
                TenantCoaAccount.account_code == AccountingJVLine.account_code,
                TenantCoaAccount.is_active.is_(True),
            ),
        )
        .outerjoin(
            CoaLedgerAccount,
            CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id,
        )
        .where(
            AccountingJVLine.tenant_id == tenant_id,
            AccountingJVAggregate.entity_id == entity_id,
            AccountingJVAggregate.period_date <= as_of_date,
            AccountingJVAggregate.status.in_([JVStatus.PUSHED, JVStatus.PUSH_IN_PROGRESS]),
        )
        .group_by(
            AccountingJVLine.account_code,
            func.coalesce(AccountingJVLine.account_name, AccountingJVLine.account_code),
            func.coalesce(
                AccountingJVLine.transaction_currency,
                AccountingJVLine.currency,
                functional_currency,
            ),
            func.coalesce(AccountingJVLine.functional_currency, functional_currency),
        )
        .order_by(AccountingJVLine.account_code.asc())
    )

    result = await db.execute(stmt)
    exposures: list[_Exposure] = []
    for row in result.all():
        transaction_currency = str(row.transaction_currency or functional_currency).upper()
        local_functional_currency = str(row.functional_currency or functional_currency).upper()
        if transaction_currency == local_functional_currency:
            continue
        is_monetary = bool(row.is_monetary) or _is_monetary_fallback(
            str(row.account_code),
            str(row.account_name),
        )
        if not is_monetary:
            continue
        exposures.append(
            _Exposure(
                account_code=str(row.account_code),
                account_name=str(row.account_name),
                transaction_currency=transaction_currency,
                functional_currency=local_functional_currency,
                foreign_balance=Decimal(str(row.foreign_balance or "0")),
                historical_base_balance=Decimal(str(row.historical_base_balance or "0")),
            )
        )
    return exposures


async def run_fx_revaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    as_of_date: date,
    initiated_by: uuid.UUID,
    actor_role: str | None = None,
) -> dict[str, object]:
    entity = await _get_entity_for_tenant(db, tenant_id=tenant_id, entity_id=entity_id)
    await assert_period_allows_revaluation(
        db,
        tenant_id=tenant_id,
        org_entity_id=entity_id,
        as_of_date=as_of_date,
        actor_role=actor_role,
    )
    exposures = await _load_monetary_exposures(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        as_of_date=as_of_date,
        functional_currency=entity.base_currency,
    )

    line_results: list[dict[str, object]] = []
    adjustment_lines: list[dict[str, object]] = []
    total_fx_difference = _ZERO

    for exposure in exposures:
        if exposure.foreign_balance == _ZERO:
            continue
        closing_rate = await get_required_latest_fx_rate(
            db,
            tenant_id=tenant_id,
            from_currency=exposure.transaction_currency,
            to_currency=exposure.functional_currency,
            rate_type="CLOSING",
            as_of_date=as_of_date,
        )
        closing_rate_value = Decimal(str(closing_rate.rate))
        revalued_base, fx_difference = compute_revaluation_delta(
            foreign_balance=exposure.foreign_balance,
            closing_rate=closing_rate_value,
            historical_base_balance=exposure.historical_base_balance,
        )

        line_results.append(
            {
                "account_code": exposure.account_code,
                "account_name": exposure.account_name,
                "transaction_currency": exposure.transaction_currency,
                "functional_currency": exposure.functional_currency,
                "foreign_balance": exposure.foreign_balance,
                "historical_base_balance": exposure.historical_base_balance,
                "closing_rate": closing_rate_value,
                "revalued_base_balance": revalued_base,
                "fx_difference": fx_difference,
            }
        )
        if fx_difference == _ZERO:
            continue

        adjustment_amount = abs(fx_difference)
        total_fx_difference += fx_difference

        if fx_difference > _ZERO:
            account_entry_type = EntryType.DEBIT
            gain_loss_entry_type = EntryType.CREDIT
        else:
            account_entry_type = EntryType.CREDIT
            gain_loss_entry_type = EntryType.DEBIT

        adjustment_lines.extend(
            [
                {
                    "account_code": exposure.account_code,
                    "account_name": exposure.account_name,
                    "entry_type": account_entry_type,
                    "amount": adjustment_amount,
                    "currency": exposure.functional_currency,
                    "transaction_currency": exposure.functional_currency,
                    "functional_currency": exposure.functional_currency,
                    "fx_rate": None,
                    "base_amount": adjustment_amount,
                    "amount_inr": adjustment_amount if exposure.functional_currency == "INR" else None,
                    "entity_id": entity_id,
                    "narration": f"FX revaluation @ {as_of_date.isoformat()}",
                },
                {
                    "account_code": _GAIN_LOSS_ACCOUNT_CODE,
                    "account_name": _GAIN_LOSS_ACCOUNT_NAME,
                    "entry_type": gain_loss_entry_type,
                    "amount": adjustment_amount,
                    "currency": exposure.functional_currency,
                    "transaction_currency": exposure.functional_currency,
                    "functional_currency": exposure.functional_currency,
                    "fx_rate": None,
                    "base_amount": adjustment_amount,
                    "amount_inr": adjustment_amount if exposure.functional_currency == "INR" else None,
                    "entity_id": entity_id,
                    "narration": f"FX revaluation offset @ {as_of_date.isoformat()}",
                },
            ]
        )

    adjustment_jv_id: uuid.UUID | None = None
    run_status = "COMPLETED_NO_ADJUSTMENT"
    if adjustment_lines:
        reval_jv = await create_jv(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            created_by=initiated_by,
            period_date=as_of_date,
            fiscal_year=as_of_date.year,
            fiscal_period=as_of_date.month,
            description=f"FX Revaluation run for {as_of_date.isoformat()}",
            reference=f"FX_REVAL:{as_of_date.isoformat()}",
            currency=entity.base_currency,
            lines=adjustment_lines,
        )
        await db.flush()
        await approve_journal(
            db,
            tenant_id=tenant_id,
            journal_id=reval_jv.id,
            acted_by=initiated_by,
            actor_role=actor_role,
        )
        await post_journal(
            db,
            tenant_id=tenant_id,
            journal_id=reval_jv.id,
            acted_by=initiated_by,
            actor_role=actor_role,
        )
        adjustment_jv_id = reval_jv.id
        run_status = "COMPLETED"

    run = await AuditWriter.insert_financial_record(
        db,
        model_class=AccountingFxRevaluationRun,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_id),
            "as_of_date": as_of_date.isoformat(),
            "status": run_status,
            "adjustment_jv_id": str(adjustment_jv_id) if adjustment_jv_id else None,
        },
        values={
            "id": uuid.uuid4(),
            "entity_id": entity_id,
            "as_of_date": as_of_date,
            "status": run_status,
            "closing_rate_source": "fx_rates",
            "initiated_by": initiated_by,
            "adjustment_jv_id": adjustment_jv_id,
        },
    )

    for row in line_results:
        await AuditWriter.insert_financial_record(
            db,
            model_class=AccountingFxRevaluationLine,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run.id),
                "account_code": str(row["account_code"]),
                "transaction_currency": str(row["transaction_currency"]),
                "fx_difference": str(row["fx_difference"]),
            },
            values={
                "id": uuid.uuid4(),
                "run_id": run.id,
                "account_code": row["account_code"],
                "account_name": row["account_name"],
                "transaction_currency": row["transaction_currency"],
                "functional_currency": row["functional_currency"],
                "foreign_balance": row["foreign_balance"],
                "historical_base_balance": row["historical_base_balance"],
                "closing_rate": row["closing_rate"],
                "revalued_base_balance": row["revalued_base_balance"],
                "fx_difference": row["fx_difference"],
            },
        )

    await db.flush()
    await record_governance_event(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        actor_user_id=initiated_by,
        module="period_close",
        action="revaluation_run",
        target_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "entity_id": str(entity_id),
            "as_of_date": as_of_date.isoformat(),
            "status": run_status,
        },
    )
    return {
        "run_id": str(run.id),
        "entity_id": str(entity_id),
        "as_of_date": as_of_date.isoformat(),
        "functional_currency": entity.base_currency,
        "status": run_status,
        "adjustment_jv_id": str(adjustment_jv_id) if adjustment_jv_id else None,
        "line_count": len(line_results),
        "total_fx_difference": str(total_fx_difference.quantize(Decimal("0.0001"))),
    }
