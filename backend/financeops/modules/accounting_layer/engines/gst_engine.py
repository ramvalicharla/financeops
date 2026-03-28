from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_tax import (
    AccountingGSTRule,
    AccountingTaxDeterminationLog,
    GSTType,
    TaxOutcome,
)
from financeops.utils.gstin import extract_state_code, validate_gstin


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _round4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass
class GSTLineResult:
    account_code: str
    gst_type: str
    amount: Decimal
    tax_code: str
    is_tax_line: bool = True


@dataclass
class GSTDetermination:
    outcome: str
    outcome_reason: str | None = None
    supplier_state_code: str | None = None
    buyer_state_code: str | None = None
    gst_sub_type: str | None = None
    base_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    cgst_amount: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_amount: Decimal | None = None
    gst_rule_id: uuid.UUID | None = None
    tax_lines: list[GSTLineResult] = field(default_factory=list)


def _get_valid_state_code(gstin: str | None) -> str | None:
    if not gstin:
        return None
    if not validate_gstin(gstin):
        return None
    return extract_state_code(gstin)


def determine_gst_type(
    supplier_gstin: str | None,
    buyer_gstin: str | None,
) -> tuple[str, str | None, str | None]:
    supplier_state = _get_valid_state_code(supplier_gstin)
    buyer_state = _get_valid_state_code(buyer_gstin)
    if supplier_state is None or buyer_state is None:
        return "MANUAL_FLAG", supplier_state, buyer_state
    if supplier_state == buyer_state:
        return "SUCCESS_INTRA", supplier_state, buyer_state
    return "SUCCESS_INTER", supplier_state, buyer_state


async def _get_applicable_gst_rule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    account_code: str,
    transaction_date: date,
) -> AccountingGSTRule | None:
    specific = await db.execute(
        select(AccountingGSTRule)
        .where(
            AccountingGSTRule.tenant_id == tenant_id,
            AccountingGSTRule.entity_id == entity_id,
            AccountingGSTRule.account_code == account_code,
            AccountingGSTRule.is_active.is_(True),
            AccountingGSTRule.effective_from <= transaction_date,
        )
        .where(
            (AccountingGSTRule.effective_to.is_(None))
            | (AccountingGSTRule.effective_to >= transaction_date)
        )
        .order_by(AccountingGSTRule.effective_from.desc(), AccountingGSTRule.created_at.desc())
        .limit(1)
    )
    rule = specific.scalar_one_or_none()
    if rule is not None:
        return rule

    wildcard = await db.execute(
        select(AccountingGSTRule)
        .where(
            AccountingGSTRule.tenant_id == tenant_id,
            AccountingGSTRule.entity_id == entity_id,
            AccountingGSTRule.account_code.is_(None),
            AccountingGSTRule.is_active.is_(True),
            AccountingGSTRule.effective_from <= transaction_date,
        )
        .where(
            (AccountingGSTRule.effective_to.is_(None))
            | (AccountingGSTRule.effective_to >= transaction_date)
        )
        .order_by(AccountingGSTRule.effective_from.desc(), AccountingGSTRule.created_at.desc())
        .limit(1)
    )
    return wildcard.scalar_one_or_none()


async def determine_gst_lines(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    jv_id: uuid.UUID,
    jv_version: int,
    account_code: str,
    base_amount: Decimal,
    transaction_date: date,
    supplier_gstin: str | None,
    buyer_gstin: str | None,
    cgst_account_code: str = "2310001",
    sgst_account_code: str = "2310002",
    igst_account_code: str = "2310003",
) -> GSTDetermination:
    gst_outcome, supplier_state, buyer_state = determine_gst_type(supplier_gstin, buyer_gstin)

    if gst_outcome == "MANUAL_FLAG":
        determination = GSTDetermination(
            outcome=TaxOutcome.MANUAL_FLAG,
            outcome_reason=(
                "Supplier or buyer GSTIN missing/invalid. Manual GST confirmation required."
            ),
            supplier_state_code=supplier_state,
            buyer_state_code=buyer_state,
            base_amount=base_amount,
            tax_amount=Decimal("0"),
        )
        await _log_determination(
            db,
            jv_id=jv_id,
            jv_version=jv_version,
            tenant_id=tenant_id,
            det=determination,
            tax_type="GST",
        )
        return determination

    rule = await _get_applicable_gst_rule(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        account_code=account_code,
        transaction_date=transaction_date,
    )

    if rule is None:
        determination = GSTDetermination(
            outcome=TaxOutcome.MANUAL_FLAG,
            outcome_reason=(
                f"No active GST rule for account '{account_code}' on {transaction_date}."
            ),
            supplier_state_code=supplier_state,
            buyer_state_code=buyer_state,
            base_amount=base_amount,
            tax_amount=Decimal("0"),
        )
        await _log_determination(
            db,
            jv_id=jv_id,
            jv_version=jv_version,
            tenant_id=tenant_id,
            det=determination,
            tax_type="GST",
        )
        return determination

    if rule.gst_type in (GSTType.EXEMPT, GSTType.NIL):
        determination = GSTDetermination(
            outcome=TaxOutcome.SKIPPED,
            outcome_reason=f"Rule type {rule.gst_type} results in no GST split.",
            supplier_state_code=supplier_state,
            buyer_state_code=buyer_state,
            gst_sub_type=rule.gst_type,
            base_amount=base_amount,
            tax_amount=Decimal("0"),
            gst_rule_id=rule.id,
        )
        await _log_determination(
            db,
            jv_id=jv_id,
            jv_version=jv_version,
            tenant_id=tenant_id,
            det=determination,
            tax_type="GST",
        )
        return determination

    total_tax = _round4(base_amount * rule.gst_rate / Decimal("100"))

    if gst_outcome == "SUCCESS_INTRA":
        half = _round4(total_tax / Decimal("2"))
        remainder = total_tax - (half * Decimal("2"))
        cgst_amount = half + remainder
        sgst_amount = half
        tax_lines = [
            GSTLineResult(
                account_code=cgst_account_code,
                gst_type=GSTType.CGST,
                amount=cgst_amount,
                tax_code=f"CGST_{rule.gst_rate}",
            ),
            GSTLineResult(
                account_code=sgst_account_code,
                gst_type=GSTType.SGST,
                amount=sgst_amount,
                tax_code=f"SGST_{rule.gst_rate}",
            ),
        ]
        determination = GSTDetermination(
            outcome=TaxOutcome.SUCCESS,
            supplier_state_code=supplier_state,
            buyer_state_code=buyer_state,
            gst_sub_type="INTRA",
            base_amount=base_amount,
            tax_amount=total_tax,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            gst_rule_id=rule.id,
            tax_lines=tax_lines,
        )
    else:
        tax_lines = [
            GSTLineResult(
                account_code=igst_account_code,
                gst_type=GSTType.IGST,
                amount=total_tax,
                tax_code=f"IGST_{rule.gst_rate}",
            )
        ]
        determination = GSTDetermination(
            outcome=TaxOutcome.SUCCESS,
            supplier_state_code=supplier_state,
            buyer_state_code=buyer_state,
            gst_sub_type="INTER",
            base_amount=base_amount,
            tax_amount=total_tax,
            igst_amount=total_tax,
            gst_rule_id=rule.id,
            tax_lines=tax_lines,
        )

    await _log_determination(
        db,
        jv_id=jv_id,
        jv_version=jv_version,
        tenant_id=tenant_id,
        det=determination,
        tax_type="GST",
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


async def _log_determination(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    jv_version: int,
    tenant_id: uuid.UUID,
    det: GSTDetermination,
    tax_type: str,
    tds_section: str | None = None,
    tds_rule_id: uuid.UUID | None = None,
) -> None:
    chain_hash, previous_hash = await _next_chain(db, tenant_id=tenant_id, jv_id=jv_id)
    log_entry = AccountingTaxDeterminationLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
        jv_id=jv_id,
        jv_version=jv_version,
        tax_type=tax_type,
        gst_sub_type=det.gst_sub_type,
        tds_section=tds_section,
        supplier_state_code=det.supplier_state_code,
        buyer_state_code=det.buyer_state_code,
        base_amount=det.base_amount,
        tax_amount=det.tax_amount,
        cgst_amount=det.cgst_amount,
        sgst_amount=det.sgst_amount,
        igst_amount=det.igst_amount,
        tds_amount=None,
        outcome=det.outcome,
        outcome_reason=det.outcome_reason,
        gst_rule_id=det.gst_rule_id,
        tds_rule_id=tds_rule_id,
        determined_at=_utcnow(),
    )
    db.add(log_entry)
    await db.flush()
