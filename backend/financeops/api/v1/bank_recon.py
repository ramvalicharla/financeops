from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.db.models.users import IamUser
from financeops.services.bank_recon_service import (
    add_bank_transaction,
    create_bank_statement,
    list_bank_recon_items,
    list_bank_statements,
    list_bank_transactions,
    run_bank_reconciliation,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateStatementRequest(BaseModel):
    bank_name: str
    account_number_masked: str
    currency: str
    period_year: int
    period_month: int
    entity_name: str
    opening_balance: Decimal
    closing_balance: Decimal
    file_name: str
    file_hash: str
    transaction_count: int = 0


class AddTransactionRequest(BaseModel):
    statement_id: UUID
    transaction_date: date
    description: str
    debit_amount: Decimal
    credit_amount: Decimal
    balance: Decimal
    reference: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/statements", status_code=status.HTTP_201_CREATED)
async def create_statement(
    body: CreateStatementRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Upload a bank statement header (INSERT ONLY)."""
    stmt = await create_bank_statement(
        session,
        tenant_id=user.tenant_id,
        bank_name=body.bank_name,
        account_number_masked=body.account_number_masked,
        currency=body.currency,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        opening_balance=body.opening_balance,
        closing_balance=body.closing_balance,
        file_name=body.file_name,
        file_hash=body.file_hash,
        uploaded_by=user.id,
        transaction_count=body.transaction_count,
    )
    await session.commit()
    return {
        "statement_id": str(stmt.id),
        "bank_name": stmt.bank_name,
        "entity_name": stmt.entity_name,
        "period": f"{stmt.period_year}-{stmt.period_month:02d}",
        "closing_balance": str(stmt.closing_balance),
        "status": stmt.status,
        "created_at": stmt.created_at.isoformat(),
    }


@router.get("/statements")
async def list_statements(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    stmts = await list_bank_statements(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        limit=limit,
        offset=offset,
    )
    return {
        "statements": [
            {
                "statement_id": str(s.id),
                "bank_name": s.bank_name,
                "entity_name": s.entity_name,
                "period": f"{s.period_year}-{s.period_month:02d}",
                "closing_balance": str(s.closing_balance),
                "transaction_count": s.transaction_count,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            }
            for s in stmts
        ],
        "count": len(stmts),
    }


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def add_transaction(
    body: AddTransactionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Add a single bank transaction row (INSERT ONLY)."""
    txn = await add_bank_transaction(
        session,
        tenant_id=user.tenant_id,
        statement_id=body.statement_id,
        transaction_date=body.transaction_date,
        description=body.description,
        debit_amount=body.debit_amount,
        credit_amount=body.credit_amount,
        balance=body.balance,
        reference=body.reference,
    )
    await session.commit()
    return {
        "transaction_id": str(txn.id),
        "transaction_date": txn.transaction_date.isoformat(),
        "debit_amount": str(txn.debit_amount),
        "credit_amount": str(txn.credit_amount),
        "match_status": txn.match_status,
        "created_at": txn.created_at.isoformat(),
    }


@router.get("/transactions/{statement_id}")
async def list_transactions(
    statement_id: UUID,
    limit: int = 200,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    txns = await list_bank_transactions(
        session,
        tenant_id=user.tenant_id,
        statement_id=statement_id,
        limit=limit,
        offset=offset,
    )
    return {
        "transactions": [
            {
                "transaction_id": str(t.id),
                "transaction_date": t.transaction_date.isoformat(),
                "description": t.description,
                "debit_amount": str(t.debit_amount),
                "credit_amount": str(t.credit_amount),
                "balance": str(t.balance),
                "match_status": t.match_status,
            }
            for t in txns
        ],
        "count": len(txns),
    }


@router.post("/run/{statement_id}", status_code=status.HTTP_201_CREATED)
async def run_bank_recon(
    statement_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Run bank reconciliation for a statement (generates open items for unmatched txns)."""
    items = await run_bank_reconciliation(
        session,
        tenant_id=user.tenant_id,
        statement_id=statement_id,
        run_by=user.id,
    )
    await session.commit()
    return {
        "statement_id": str(statement_id),
        "open_items_created": len(items),
        "items": [
            {
                "item_id": str(i.id),
                "item_type": i.item_type,
                "amount": str(i.amount),
                "status": i.status,
            }
            for i in items
        ],
    }


@router.get("/items")
async def list_recon_items(
    statement_id: UUID | None = None,
    item_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    items = await list_bank_recon_items(
        session,
        tenant_id=user.tenant_id,
        statement_id=statement_id,
        status=item_status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "item_id": str(i.id),
                "item_type": i.item_type,
                "amount": str(i.amount),
                "status": i.status,
                "entity_name": i.entity_name,
                "period": f"{i.period_year}-{i.period_month:02d}",
            }
            for i in items
        ],
        "count": len(items),
    }
