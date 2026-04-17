from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.db.models.accounting_jv import (
    AccountingJVAggregate,
    AccountingJVLine,
    EntryType,
    JVStatus,
)
from financeops.db.models.bank_recon import BankStatement, BankTransaction, BankReconItem
from financeops.modules.bank_reconciliation.domain.exceptions import (
    InsufficientDataError,
    StatementAlreadyProcessedError,
)
from financeops.modules.bank_reconciliation.parsers.base import BankTransaction as ParsedBankTransaction
from financeops.modules.coa.models import CoaAccountSubgroup, TenantCoaAccount
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)
_ZERO = Decimal("0")
_FUZZY_AMOUNT_TOLERANCE = Decimal("0.0001")
_CANDIDATE_TEXT_TOKENS = ("BANK", "CASH", "CURRENT ACCOUNT", "PETTY CASH", "EEFC")


@dataclass(slots=True)
class BankReconSummary:
    matched: int = 0
    near_match: int = 0
    fuzzy: int = 0
    bank_only: int = 0
    gl_only: int = 0
    net_difference: Decimal = _ZERO


@dataclass(slots=True)
class BankReconRunResult:
    items: list[BankReconItem]
    summary: BankReconSummary


@dataclass(slots=True)
class _BankTxnCandidate:
    txn_id: uuid.UUID
    amount: Decimal
    value_date: date
    description: str


@dataclass(slots=True)
class _GlLineCandidate:
    line_id: uuid.UUID
    reference: str
    amount: Decimal
    posting_date: date
    narration: str


@dataclass(slots=True)
class _PendingReconItem:
    item_type: str
    amount: Decimal
    bank_transaction_id: uuid.UUID | None
    gl_reference: str | None
    notes: str | None = None


async def _resolve_or_create_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    entity_name: str | None,
) -> tuple[uuid.UUID, str]:
    resolved_id = entity_id
    resolved_name = entity_name

    if resolved_id is not None:
        row = (
            await session.execute(
                select(CpEntity.entity_name).where(
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.id == resolved_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None and not resolved_name:
            resolved_name = row
        if row is not None and resolved_name:
            return resolved_id, resolved_name

    first_entity = (
        await session.execute(
            select(CpEntity.id, CpEntity.entity_name)
            .where(CpEntity.tenant_id == tenant_id)
            .order_by(CpEntity.created_at.asc())
            .limit(1)
        )
    ).first()
    if first_entity is not None:
        return first_entity[0], resolved_name or first_entity[1]

    org = (
        await session.execute(
            select(CpOrganisation)
            .where(CpOrganisation.tenant_id == tenant_id)
            .order_by(CpOrganisation.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if org is None:
        org_code = f"AUTO_ORG_{str(tenant_id).replace('-', '')[:16].upper()}"
        org = CpOrganisation(
            tenant_id=tenant_id,
            organisation_code=org_code,
            organisation_name="Auto Organisation",
            parent_organisation_id=None,
            supersedes_id=None,
            is_active=True,
            correlation_id="bank-recon-auto",
            chain_hash=compute_chain_hash({"organisation_code": org_code}, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(org)
        await session.flush()

    entity_code = f"AUTO_ENT_{str(tenant_id).replace('-', '')[:16].upper()}"
    entity = CpEntity(
        tenant_id=tenant_id,
        entity_code=entity_code,
        entity_name=resolved_name or "Auto Entity",
        organisation_id=org.id,
        group_id=None,
        base_currency="INR",
        country_code="IN",
        status="active",
        deactivated_at=None,
        correlation_id="bank-recon-auto",
        chain_hash=compute_chain_hash({"entity_code": entity_code}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()
    return entity.id, entity.entity_name


async def create_bank_statement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    bank_name: str,
    account_number_masked: str,
    currency: str,
    period_year: int,
    period_month: int,
    entity_id: uuid.UUID | None = None,
    entity_name: str | None = None,
    opening_balance: Decimal,
    closing_balance: Decimal,
    file_name: str,
    file_hash: str,
    uploaded_by: uuid.UUID,
    transaction_count: int = 0,
    location_id: uuid.UUID | None = None,
    cost_centre_id: uuid.UUID | None = None,
) -> BankStatement:
    """Create a bank statement header record (INSERT ONLY)."""
    require_mutation_context("Bank statement creation")
    resolved_entity_id, resolved_entity_name = await _resolve_or_create_entity(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        entity_name=entity_name,
    )

    previous_hash = await get_previous_hash_locked(session, BankStatement, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "bank_name": bank_name,
        "account_number_masked": account_number_masked,
        "period_year": period_year,
        "period_month": period_month,
        "entity_id": str(resolved_entity_id),
        "entity_name": resolved_entity_name,
        "file_hash": file_hash,
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    stmt = apply_mutation_linkage(BankStatement(
        tenant_id=tenant_id,
        bank_name=bank_name,
        account_number_masked=account_number_masked,
        currency=currency,
        period_year=period_year,
        period_month=period_month,
        entity_id=resolved_entity_id,
        entity_name=resolved_entity_name,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        transaction_count=transaction_count,
        file_name=file_name,
        file_hash=file_hash,
        status="pending",
        uploaded_by=uploaded_by,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    ))
    session.add(stmt)
    await session.flush()
    return stmt


async def add_bank_transaction(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    transaction_date: date,
    description: str,
    debit_amount: Decimal,
    credit_amount: Decimal,
    balance: Decimal,
    reference: str | None = None,
) -> BankTransaction:
    """Add a single bank transaction row (INSERT ONLY)."""
    require_mutation_context("Bank transaction creation")
    resolved_entity_id = entity_id
    if resolved_entity_id is None:
        resolved_entity_id = (
            await session.execute(
                select(BankStatement.entity_id).where(
                    BankStatement.tenant_id == tenant_id,
                    BankStatement.id == statement_id,
                )
            )
        ).scalar_one_or_none()
        if resolved_entity_id is None:
            raise ValueError("entity_id is required when statement is missing")

    previous_hash = await get_previous_hash_locked(session, BankTransaction, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "statement_id": str(statement_id),
        "entity_id": str(resolved_entity_id),
        "transaction_date": str(transaction_date),
        "debit_amount": str(debit_amount),
        "credit_amount": str(credit_amount),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    txn = apply_mutation_linkage(BankTransaction(
        tenant_id=tenant_id,
        statement_id=statement_id,
        entity_id=resolved_entity_id,
        transaction_date=transaction_date,
        description=description,
        debit_amount=debit_amount,
        credit_amount=credit_amount,
        balance=balance,
        reference=reference,
        match_status="unmatched",
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    ))
    session.add(txn)
    await session.flush()
    return txn


async def run_bank_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    run_by: uuid.UUID,
    force_rerun: bool = False,
) -> BankReconRunResult:
    """
    Run bank reconciliation against bank-side GL lines using a three-pass matcher:
    exact -> near-date -> fuzzy-description.

    BankStatement, BankTransaction, and BankReconItem remain append-only.
    Reruns therefore append new recon items instead of mutating prior rows.
    """
    require_mutation_context("Bank reconciliation run")
    result = await session.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        return BankReconRunResult(items=[], summary=BankReconSummary())

    if not force_rerun:
        existing_count = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(BankReconItem)
                    .where(
                        BankReconItem.tenant_id == tenant_id,
                        BankReconItem.statement_id == statement_id,
                    )
                )
            ).scalar_one()
        )
        if existing_count > 0:
            raise StatementAlreadyProcessedError(statement_id)

    txns_result = await session.execute(
        select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.match_status == "unmatched",
        )
    )
    unmatched_txns = list(txns_result.scalars().all())
    if not unmatched_txns:
        return BankReconRunResult(items=[], summary=BankReconSummary())

    bank_candidates = [
        _BankTxnCandidate(
            txn_id=txn.id,
            amount=_signed_bank_amount(txn),
            value_date=txn.transaction_date,
            description=txn.description or "",
        )
        for txn in unmatched_txns
    ]
    if not bank_candidates:
        return BankReconRunResult(items=[], summary=BankReconSummary())

    min_date = min(candidate.value_date for candidate in bank_candidates)
    max_date = max(candidate.value_date for candidate in bank_candidates)
    gl_candidates = await _load_gl_candidates(
        session,
        tenant_id=tenant_id,
        entity_id=stmt.entity_id,
        from_date=min_date - timedelta(days=7),
        to_date=max_date + timedelta(days=7),
    )

    summary = BankReconSummary()
    pending_items: list[_PendingReconItem] = []
    remaining_bank = list(bank_candidates)
    remaining_gl = {candidate.reference: candidate for candidate in gl_candidates}
    gl_exact_index = _build_gl_exact_index(gl_candidates)
    gl_near_index = _build_gl_near_index(gl_candidates)

    pass_one_unmatched: list[_BankTxnCandidate] = []
    for bank_candidate in remaining_bank:
        key = (bank_candidate.amount, bank_candidate.value_date)
        matched_gl = _take_from_exact_index(gl_exact_index.get(key, []), remaining_gl)
        if matched_gl is None:
            pass_one_unmatched.append(bank_candidate)
            continue
        _remove_from_near_index(gl_near_index, matched_gl)
        pending_items.append(
            _PendingReconItem(
                item_type="matched",
                amount=bank_candidate.amount,
                bank_transaction_id=bank_candidate.txn_id,
                gl_reference=matched_gl.reference,
                notes="exact amount/date match",
            )
        )
        summary.matched += 1

    pass_two_unmatched: list[_BankTxnCandidate] = []
    for bank_candidate in pass_one_unmatched:
        matched_gl = _find_near_match(
            bank_candidate,
            gl_near_index.get(bank_candidate.amount, []),
            remaining_gl,
        )
        if matched_gl is None:
            pass_two_unmatched.append(bank_candidate)
            continue
        remaining_gl.pop(matched_gl.reference, None)
        _remove_from_near_index(gl_near_index, matched_gl)
        pending_items.append(
            _PendingReconItem(
                item_type="near_match",
                amount=bank_candidate.amount,
                bank_transaction_id=bank_candidate.txn_id,
                gl_reference=matched_gl.reference,
                notes="amount match within 3 days",
            )
        )
        summary.near_match += 1

    pass_three_unmatched: list[_BankTxnCandidate] = []
    for bank_candidate in pass_two_unmatched:
        matched_gl = _find_fuzzy_match(bank_candidate, remaining_gl.values())
        if matched_gl is None:
            pass_three_unmatched.append(bank_candidate)
            continue
        remaining_gl.pop(matched_gl.reference, None)
        _remove_from_near_index(gl_near_index, matched_gl)
        pending_items.append(
            _PendingReconItem(
                item_type="fuzzy_match",
                amount=bank_candidate.amount,
                bank_transaction_id=bank_candidate.txn_id,
                gl_reference=matched_gl.reference,
                notes="description similarity > 0.80",
            )
        )
        summary.fuzzy += 1

    for bank_candidate in pass_three_unmatched:
        pending_items.append(
            _PendingReconItem(
                item_type="bank_only",
                amount=bank_candidate.amount,
                bank_transaction_id=bank_candidate.txn_id,
                gl_reference=None,
            )
        )
        summary.bank_only += 1
        summary.net_difference += bank_candidate.amount

    for gl_candidate in remaining_gl.values():
        pending_items.append(
            _PendingReconItem(
                item_type="gl_only",
                amount=gl_candidate.amount,
                bank_transaction_id=None,
                gl_reference=gl_candidate.reference,
            )
        )
        summary.gl_only += 1
        summary.net_difference -= gl_candidate.amount

    items = await _append_recon_items(
        session,
        tenant_id=tenant_id,
        statement=stmt,
        pending_items=pending_items,
        run_by=run_by,
    )

    log.info(
        "Bank recon run: tenant=%s statement=%s matched=%d near=%d fuzzy=%d bank_only=%d gl_only=%d",
        str(tenant_id)[:8],
        str(statement_id)[:8],
        summary.matched,
        summary.near_match,
        summary.fuzzy,
        summary.bank_only,
        summary.gl_only,
    )
    return BankReconRunResult(items=items, summary=summary)


async def list_bank_statements(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_id: uuid.UUID | None = None,
    entity_name: str | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> list[BankStatement]:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(BankStatement).where(BankStatement.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(BankStatement.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(BankStatement.period_month == period_month)
    if entity_id is not None:
        stmt = stmt.where(BankStatement.entity_id == entity_id)
    if entity_name:
        stmt = stmt.where(BankStatement.entity_name == entity_name)
    stmt = stmt.order_by(desc(BankStatement.created_at)).limit(bounded_limit).offset(effective_skip)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_bank_transactions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    entity_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> list[BankTransaction]:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    result = await session.execute(
        select(BankTransaction)
        .where(
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.statement_id == statement_id,
            BankTransaction.entity_id == entity_id,
        )
        .order_by(BankTransaction.transaction_date)
        .limit(bounded_limit)
        .offset(effective_skip)
    )
    return list(result.scalars().all())


async def list_bank_recon_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    statement_id: uuid.UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> list[BankReconItem]:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(BankReconItem).where(BankReconItem.tenant_id == tenant_id)
    if entity_id is not None:
        stmt = stmt.where(BankReconItem.entity_id == entity_id)
    if statement_id:
        stmt = stmt.where(BankReconItem.statement_id == statement_id)
    if status:
        stmt = stmt.where(BankReconItem.status == status)
    stmt = stmt.order_by(desc(BankReconItem.created_at)).limit(bounded_limit).offset(effective_skip)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def store_bank_transactions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    entity_name: str,
    bank_name: str,
    transactions: list[ParsedBankTransaction],
    uploaded_by: uuid.UUID,
    admitted_airlock_item_id: uuid.UUID,
    source_type: str,
) -> list[BankTransaction]:
    require_mutation_context("Bank statement import")
    if not transactions:
        return []
    await AirlockAdmissionService().assert_admitted(
        session,
        tenant_id=tenant_id,
        item_id=admitted_airlock_item_id,
        source_type=source_type,
    )

    first = min(t.transaction_date for t in transactions)
    last = max(t.transaction_date for t in transactions)
    statement = await create_bank_statement(
        session,
        tenant_id=tenant_id,
        bank_name=bank_name,
        account_number_masked="****0000",
        currency="INR",
        period_year=last.year,
        period_month=last.month,
        entity_id=entity_id,
        entity_name=entity_name,
        opening_balance=transactions[0].balance or Decimal("0.00"),
        closing_balance=transactions[-1].balance or Decimal("0.00"),
        file_name=f"{bank_name}_{first.isoformat()}_{last.isoformat()}.csv",
        file_hash=compute_chain_hash(
            {
                "tenant_id": str(tenant_id),
                "bank_name": bank_name,
                "first": first.isoformat(),
                "last": last.isoformat(),
                "count": len(transactions),
            },
            None,
        ),
        uploaded_by=uploaded_by,
        transaction_count=len(transactions),
    )

    stored: list[BankTransaction] = []
    for txn in transactions:
        row = await add_bank_transaction(
            session,
            tenant_id=tenant_id,
            statement_id=statement.id,
            entity_id=entity_id,
            transaction_date=txn.transaction_date,
            description=txn.description,
            debit_amount=txn.debit or Decimal("0.00"),
            credit_amount=txn.credit or Decimal("0.00"),
            balance=txn.balance or Decimal("0.00"),
            reference=txn.reference or None,
        )
        stored.append(row)
    return stored


def _signed_bank_amount(txn: BankTransaction) -> Decimal:
    return Decimal(txn.credit_amount or _ZERO) - Decimal(txn.debit_amount or _ZERO)


def _signed_gl_amount(line: AccountingJVLine) -> Decimal:
    amount = Decimal(line.amount or _ZERO)
    if line.entry_type == EntryType.CREDIT:
        return -amount
    return amount


def _gl_reference(jv_id: uuid.UUID, line_number: int) -> str:
    return f"{jv_id}:{line_number}"


async def _load_gl_candidates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    from_date: date,
    to_date: date,
) -> list[_GlLineCandidate]:
    bank_account_codes = await _find_bank_account_codes(session, tenant_id=tenant_id)
    status_filter = tuple(
        status for status in JVStatus.IMMUTABLE_STATES if status != JVStatus.VOIDED
    )
    stmt = (
        select(AccountingJVLine, AccountingJVAggregate)
        .join(AccountingJVAggregate, AccountingJVAggregate.id == AccountingJVLine.jv_id)
        .where(
            AccountingJVLine.tenant_id == tenant_id,
            AccountingJVAggregate.tenant_id == tenant_id,
            AccountingJVLine.entity_id == entity_id,
            AccountingJVAggregate.entity_id == entity_id,
            AccountingJVAggregate.period_date >= from_date,
            AccountingJVAggregate.period_date <= to_date,
            AccountingJVAggregate.status.in_(status_filter),
        )
        .order_by(AccountingJVAggregate.period_date.asc(), AccountingJVLine.line_number.asc())
    )

    if bank_account_codes:
        stmt = stmt.where(AccountingJVLine.account_code.in_(sorted(bank_account_codes)))
    else:
        stmt = stmt.where(_fallback_bank_account_predicate())

    result = await session.execute(stmt)
    rows = result.all()
    return [
        _GlLineCandidate(
            line_id=line.id,
            reference=_gl_reference(jv.id, line.line_number),
            amount=_signed_gl_amount(line),
            posting_date=jv.period_date,
            narration=str(
                line.narration
                or jv.description
                or jv.reference
                or jv.external_reference_id
                or line.account_name
                or ""
            ),
        )
        for line, jv in rows
    ]


async def _find_bank_account_codes(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> set[str]:
    result = await session.execute(
        select(TenantCoaAccount.account_code)
        .join(CoaAccountSubgroup, CoaAccountSubgroup.id == TenantCoaAccount.parent_subgroup_id)
        .where(
            TenantCoaAccount.tenant_id == tenant_id,
            TenantCoaAccount.is_active.is_(True),
            CoaAccountSubgroup.code == "CASH_EQUIVALENTS",
        )
    )
    return {str(value) for value in result.scalars().all() if value}


def _fallback_bank_account_predicate():
    account_name = func.upper(func.coalesce(AccountingJVLine.account_name, ""))
    narration = func.upper(func.coalesce(AccountingJVLine.narration, ""))
    jv_description = func.upper(func.coalesce(AccountingJVAggregate.description, ""))
    return or_(
        *([account_name.like(f"%{token}%") for token in _CANDIDATE_TEXT_TOKENS]),
        *([narration.like(f"%{token}%") for token in _CANDIDATE_TEXT_TOKENS]),
        *([jv_description.like(f"%{token}%") for token in _CANDIDATE_TEXT_TOKENS]),
    )


def _build_gl_exact_index(
    gl_candidates: list[_GlLineCandidate],
) -> dict[tuple[Decimal, date], list[str]]:
    gl_exact_index: dict[tuple[Decimal, date], list[str]] = {}
    for gl_candidate in gl_candidates:
        key = (gl_candidate.amount, gl_candidate.posting_date)
        gl_exact_index.setdefault(key, []).append(gl_candidate.reference)
    return gl_exact_index


def _build_gl_near_index(gl_candidates: list[_GlLineCandidate]) -> dict[Decimal, list[str]]:
    gl_near_index: dict[Decimal, list[str]] = {}
    for gl_candidate in gl_candidates:
        gl_near_index.setdefault(gl_candidate.amount, []).append(gl_candidate.reference)
    return gl_near_index


def _take_from_exact_index(
    candidate_refs: list[str],
    remaining_gl: dict[str, _GlLineCandidate],
) -> _GlLineCandidate | None:
    while candidate_refs:
        candidate_ref = candidate_refs.pop(0)
        candidate = remaining_gl.pop(candidate_ref, None)
        if candidate is not None:
            return candidate
    return None


def _remove_from_near_index(
    gl_near_index: dict[Decimal, list[str]],
    gl_candidate: _GlLineCandidate,
) -> None:
    candidates = gl_near_index.get(gl_candidate.amount)
    if not candidates:
        return
    gl_near_index[gl_candidate.amount] = [
        candidate_ref for candidate_ref in candidates if candidate_ref != gl_candidate.reference
    ]


def _find_near_match(
    bank_candidate: _BankTxnCandidate,
    candidate_refs: list[str],
    remaining_gl: dict[str, _GlLineCandidate],
) -> _GlLineCandidate | None:
    while candidate_refs:
        candidate_ref = candidate_refs.pop(0)
        gl_candidate = remaining_gl.get(candidate_ref)
        if gl_candidate is None:
            continue
        if abs((bank_candidate.value_date - gl_candidate.posting_date).days) <= 3:
            remaining_gl.pop(candidate_ref, None)
            return gl_candidate
    return None


def _find_fuzzy_match(
    bank_candidate: _BankTxnCandidate,
    remaining_gl_candidates,
) -> _GlLineCandidate | None:
    for gl_candidate in remaining_gl_candidates:
        if gl_candidate.amount == _ZERO:
            continue
        relative_delta = abs(bank_candidate.amount - gl_candidate.amount) / abs(gl_candidate.amount)
        if relative_delta >= _FUZZY_AMOUNT_TOLERANCE:
            continue
        if abs((bank_candidate.value_date - gl_candidate.posting_date).days) > 7:
            continue
        ratio = SequenceMatcher(
            None,
            bank_candidate.description or "",
            gl_candidate.narration or "",
        ).ratio()
        if ratio > 0.8:
            return gl_candidate
    return None


async def _append_recon_items(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement: BankStatement,
    pending_items: list[_PendingReconItem],
    run_by: uuid.UUID,
) -> list[BankReconItem]:
    if not pending_items:
        return []

    previous_hash = await get_previous_hash_locked(session, BankReconItem, tenant_id)
    items: list[BankReconItem] = []
    for pending_item in pending_items:
        record_data = {
            "tenant_id": str(tenant_id),
            "statement_id": str(statement.id),
            "bank_transaction_id": str(pending_item.bank_transaction_id) if pending_item.bank_transaction_id else None,
            "gl_reference": pending_item.gl_reference,
            "item_type": pending_item.item_type,
            "amount": str(pending_item.amount),
        }
        chain_hash = compute_chain_hash(record_data, previous_hash)
        item = apply_mutation_linkage(BankReconItem(
            tenant_id=tenant_id,
            statement_id=statement.id,
            period_year=statement.period_year,
            period_month=statement.period_month,
            entity_id=statement.entity_id,
            entity_name=statement.entity_name,
            item_type=pending_item.item_type,
            bank_transaction_id=pending_item.bank_transaction_id,
            gl_reference=pending_item.gl_reference,
            amount=pending_item.amount,
            status="open",
            notes=pending_item.notes,
            run_by=run_by,
            chain_hash=chain_hash,
            previous_hash=previous_hash,
        ))
        session.add(item)
        items.append(item)
        previous_hash = chain_hash
    await session.flush()
    return items

