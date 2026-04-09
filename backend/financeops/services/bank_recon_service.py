from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.db.models.bank_recon import BankStatement, BankTransaction, BankReconItem
from financeops.modules.bank_reconciliation.parsers.base import BankTransaction as ParsedBankTransaction
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)


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
) -> list[BankReconItem]:
    """
    Run basic bank reconciliation: create BankReconItem for each unmatched transaction.
    In Phase 1, all unmatched transactions become 'bank_only' open items.
    """
    require_mutation_context("Bank reconciliation run")
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

        item = apply_mutation_linkage(BankReconItem(
            tenant_id=tenant_id,
            statement_id=statement_id,
            period_year=stmt.period_year,
            period_month=stmt.period_month,
            entity_id=stmt.entity_id,
            entity_name=stmt.entity_name,
            item_type="bank_only",
            bank_transaction_id=txn.id,
            gl_reference=None,
            amount=amount,
            status="open",
            run_by=run_by,
            chain_hash=chain_hash,
            previous_hash=previous_hash,
        ))
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

