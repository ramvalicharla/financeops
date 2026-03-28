from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_tax import (
    AccountingTDSRule,
    AccountingTaxDeterminationLog,
    TaxOutcome,
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _round4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass
class TDSLineResult:
    account_code: str
    tds_section: str
    amount: Decimal
    tax_code: str
    is_tax_line: bool = True


@dataclass
class TDSDetermination:
    outcome: str
    outcome_reason: str | None = None
    tds_section: str | None = None
    base_amount: Decimal = Decimal("0")
    tds_amount: Decimal = Decimal("0")
    tds_rule_id: uuid.UUID | None = None
    tax_lines: list[TDSLineResult] = field(default_factory=list)


async def _get_applicable_tds_rule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    vendor_id: uuid.UUID | None,
    tds_section: str,
    transaction_date: date,
) -> AccountingTDSRule | None:
    if vendor_id is not None:
        vendor_rule = await db.execute(
            select(AccountingTDSRule)
            .where(
                AccountingTDSRule.tenant_id == tenant_id,
                AccountingTDSRule.entity_id == entity_id,
                AccountingTDSRule.vendor_id == vendor_id,
                AccountingTDSRule.tds_section == tds_section,
                AccountingTDSRule.is_active.is_(True),
                AccountingTDSRule.effective_from <= transaction_date,
            )
            .where(
                (AccountingTDSRule.effective_to.is_(None))
                | (AccountingTDSRule.effective_to >= transaction_date)
            )
            .order_by(AccountingTDSRule.effective_from.desc(), AccountingTDSRule.created_at.desc())
            .limit(1)
        )
        match = vendor_rule.scalar_one_or_none()
        if match is not None:
            return match

    entity_rule = await db.execute(
        select(AccountingTDSRule)
        .where(
            AccountingTDSRule.tenant_id == tenant_id,
            AccountingTDSRule.entity_id == entity_id,
            AccountingTDSRule.vendor_id.is_(None),
            AccountingTDSRule.tds_section == tds_section,
            AccountingTDSRule.is_active.is_(True),
            AccountingTDSRule.effective_from <= transaction_date,
        )
        .where(
            (AccountingTDSRule.effective_to.is_(None))
            | (AccountingTDSRule.effective_to >= transaction_date)
        )
        .order_by(AccountingTDSRule.effective_from.desc(), AccountingTDSRule.created_at.desc())
        .limit(1)
    )
    return entity_rule.scalar_one_or_none()


async def determine_tds_line(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    jv_id: uuid.UUID,
    jv_version: int,
    vendor_id: uuid.UUID | None,
    tds_section: str,
    base_amount: Decimal,
    transaction_date: date,
    tds_payable_account_code: str = "2320001",
) -> TDSDetermination:
    rule = await _get_applicable_tds_rule(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        vendor_id=vendor_id,
        tds_section=tds_section,
        transaction_date=transaction_date,
    )

    if rule is None:
        determination = TDSDetermination(
            outcome=TaxOutcome.MANUAL_FLAG,
            outcome_reason=(
                f"No active TDS rule found for section '{tds_section}' on {transaction_date}."
            ),
            tds_section=tds_section,
            base_amount=base_amount,
            tds_amount=Decimal("0"),
        )
        await _log_tds_determination(
            db,
            jv_id=jv_id,
            jv_version=jv_version,
            tenant_id=tenant_id,
            det=determination,
        )
        return determination

    tds_amount = _round4(base_amount * rule.tds_rate / Decimal("100"))
    surcharge = _round4(tds_amount * rule.surcharge_rate / Decimal("100"))
    cess = _round4((tds_amount + surcharge) * rule.cess_rate / Decimal("100"))
    total_tds = _round4(tds_amount + surcharge + cess)

    determination = TDSDetermination(
        outcome=TaxOutcome.SUCCESS,
        tds_section=tds_section,
        base_amount=base_amount,
        tds_amount=total_tds,
        tds_rule_id=rule.id,
        tax_lines=[
            TDSLineResult(
                account_code=tds_payable_account_code,
                tds_section=tds_section,
                amount=total_tds,
                tax_code=f"TDS_{tds_section}_{rule.tds_rate}",
            )
        ],
    )
    await _log_tds_determination(
        db,
        jv_id=jv_id,
        jv_version=jv_version,
        tenant_id=tenant_id,
        det=determination,
    )
    return determination


async def _next_chain(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv_id: uuid.UUID,
) -> tuple[str, str]:
    previous = await db.execute(
        select(AccountingTaxDeterminationLog)
        .where(
            AccountingTaxDeterminationLog.tenant_id == tenant_id,
            AccountingTaxDeterminationLog.jv_id == jv_id,
        )
        .order_by(
            AccountingTaxDeterminationLog.created_at.desc(),
            AccountingTaxDeterminationLog.id.desc(),
        )
        .limit(1)
    )
    prev_row = previous.scalar_one_or_none()
    previous_hash = prev_row.chain_hash if prev_row is not None else "0" * 64
    chain_hash = hashlib.sha256(
        f"{previous_hash}:{jv_id}:{_utcnow().isoformat()}".encode()
    ).hexdigest()
    return chain_hash, previous_hash


async def _log_tds_determination(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    jv_version: int,
    tenant_id: uuid.UUID,
    det: TDSDetermination,
) -> None:
    chain_hash, previous_hash = await _next_chain(db, tenant_id=tenant_id, jv_id=jv_id)
    log_entry = AccountingTaxDeterminationLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
        jv_id=jv_id,
        jv_version=jv_version,
        tax_type="TDS",
        gst_sub_type=None,
        tds_section=det.tds_section,
        supplier_state_code=None,
        buyer_state_code=None,
        base_amount=det.base_amount,
        tax_amount=det.tds_amount,
        cgst_amount=None,
        sgst_amount=None,
        igst_amount=None,
        tds_amount=det.tds_amount,
        outcome=det.outcome,
        outcome_reason=det.outcome_reason,
        gst_rule_id=None,
        tds_rule_id=det.tds_rule_id,
        determined_at=_utcnow(),
    )
    db.add(log_entry)
    await db.flush()
