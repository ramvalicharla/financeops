from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.bank_recon import BankStatement, BankTransaction, BankReconItem
from financeops.modules.bank_reconciliation.parsers.base import BankTransaction as ParsedBankTransaction
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)


async def create_bank_statement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    bank_name: str,
    account_number_masked: str,
    currency: str,
    period_year: int,
    period_month: int,
    entity_name: str,
    opening_balance: Decimal,
    closing_balance: Decimal,
    file_name: str,
    file_hash: str,
    uploaded_by: uuid.UUID,
    transaction_count: int = 0,
) -> BankStatement:
    """Create a bank statement header record (INSERT ONLY)."""
    previous_hash = await get_previous_hash_locked(session, BankStatement, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "bank_name": bank_name,
        "account_number_masked": account_number_masked,
        "period_year": period_year,
        "period_month": period_month,
        "entity_name": entity_name,
        "file_hash": file_hash,
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    stmt = BankStatement(
        tenant_id=tenant_id,
        bank_name=bank_name,
        account_number_masked=account_number_masked,
        currency=currency,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        transaction_count=transaction_count,
        file_name=file_name,
        file_hash=file_hash,
        status="pending",
        uploaded_by=uploaded_by,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(stmt)
    await session.flush()
    return stmt


async def add_bank_transaction(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    transaction_date: date,
    description: str,
    debit_amount: Decimal,
    credit_amount: Decimal,
    balance: Decimal,
    reference: str | None = None,
) -> BankTransaction:
    """Add a single bank transaction row (INSERT ONLY)."""
    previous_hash = await get_previous_hash_locked(session, BankTransaction, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "statement_id": str(statement_id),
        "transaction_date": str(transaction_date),
        "debit_amount": str(debit_amount),
        "credit_amount": str(credit_amount),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    txn = BankTransaction(
        tenant_id=tenant_id,
        statement_id=statement_id,
        transaction_date=transaction_date,
        description=description,
        debit_amount=debit_amount,
        credit_amount=credit_amount,
        balance=balance,
        reference=reference,
        match_status="unmatched",
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(txn)
    await session.flush()
    return txn


async def run_bank_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    run_by: uuid.UUID,
) -> list[BankReconItem]:
    """
    Run basic bank reconciliation: create BankReconItem for each unmatched transaction.
    In Phase 1, all unmatched transactions become 'bank_only' open items.
    """
    # Fetch statement header
    result = await session.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        return []

    # Get all unmatched transactions for this statement
    txns_result = await session.execute(
        select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.match_status == "unmatched",
        )
    )
    unmatched_txns = list(txns_result.scalars().all())

    items: list[BankReconItem] = []
    for txn in unmatched_txns:
        amount = txn.credit_amount - txn.debit_amount

        previous_hash = await get_previous_hash_locked(session, BankReconItem, tenant_id)
        record_data = {
            "tenant_id": str(tenant_id),
            "statement_id": str(statement_id),
            "bank_transaction_id": str(txn.id),
            "amount": str(amount),
        }
        chain_hash = compute_chain_hash(record_data, previous_hash)

        item = BankReconItem(
            tenant_id=tenant_id,
            statement_id=statement_id,
            period_year=stmt.period_year,
            period_month=stmt.period_month,
            entity_name=stmt.entity_name,
            item_type="bank_only",
            bank_transaction_id=txn.id,
            gl_reference=None,
            amount=amount,
            status="open",
            run_by=run_by,
            chain_hash=chain_hash,
            previous_hash=previous_hash,
        )
        session.add(item)
        items.append(item)

    if items:
        await session.flush()

    log.info(
        "Bank recon run: tenant=%s statement=%s open_items=%d",
        str(tenant_id)[:8], str(statement_id)[:8], len(items),
    )
    return items


async def list_bank_statements(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BankStatement]:
    stmt = select(BankStatement).where(BankStatement.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(BankStatement.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(BankStatement.period_month == period_month)
    if entity_name:
        stmt = stmt.where(BankStatement.entity_name == entity_name)
    stmt = stmt.order_by(desc(BankStatement.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_bank_transactions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID,
    limit: int = 200,
    offset: int = 0,
) -> list[BankTransaction]:
    result = await session.execute(
        select(BankTransaction)
        .where(BankTransaction.tenant_id == tenant_id, BankTransaction.statement_id == statement_id)
        .order_by(BankTransaction.transaction_date)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_bank_recon_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    statement_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[BankReconItem]:
    stmt = select(BankReconItem).where(BankReconItem.tenant_id == tenant_id)
    if statement_id:
        stmt = stmt.where(BankReconItem.statement_id == statement_id)
    if status:
        stmt = stmt.where(BankReconItem.status == status)
    stmt = stmt.order_by(desc(BankReconItem.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def store_bank_transactions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    bank_name: str,
    transactions: list[ParsedBankTransaction],
    uploaded_by: uuid.UUID,
) -> list[BankTransaction]:
    if not transactions:
        return []

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
        entity_name="default",
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
            transaction_date=txn.transaction_date,
            description=txn.description,
            debit_amount=txn.debit or Decimal("0.00"),
            credit_amount=txn.credit or Decimal("0.00"),
            balance=txn.balance or Decimal("0.00"),
            reference=txn.reference or None,
        )
        stored.append(row)
    return stored

