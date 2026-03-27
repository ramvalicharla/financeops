from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.db.models.bank_recon import BankReconItem, BankStatement, BankTransaction
from financeops.db.models.users import IamUser
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.services.context_resolver import resolve_entity_id
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.modules.bank_reconciliation.parsers.factory import (
    detect_bank_from_content,
    get_parser,
)
from financeops.services.bank_recon_service import (
    add_bank_transaction,
    create_bank_statement,
    list_bank_recon_items,
    list_bank_statements,
    list_bank_transactions,
    run_bank_reconciliation,
    store_bank_transactions,
)

log = logging.getLogger(__name__)
router = APIRouter()


class CreateStatementRequest(BaseModel):
    bank_name: str
    account_number_masked: str
    currency: str
    period_year: int
    period_month: int
    entity_id: UUID | None = None
    entity_name: str | None = None
    location_id: UUID | None = None
    cost_centre_id: UUID | None = None
    opening_balance: Decimal
    closing_balance: Decimal
    file_name: str
    file_hash: str
    transaction_count: int = 0


class AddTransactionRequest(BaseModel):
    statement_id: UUID
    entity_id: UUID | None = None
    transaction_date: date
    description: str
    debit_amount: Decimal
    credit_amount: Decimal
    balance: Decimal
    reference: str | None = None


@router.post("/upload-statement")
async def upload_bank_statement(
    bank_name: str,
    entity_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    Upload and parse a bank statement CSV.
    Supported banks: HDFC, ICICI, SBI, Axis
    """
    content = (await file.read()).decode("utf-8", errors="replace")

    if bank_name == "auto":
        bank_name = detect_bank_from_content(content)

    parser = get_parser(bank_name)
    transactions = parser.parse_csv(content)

    if not transactions:
        raise HTTPException(
            status_code=400,
            detail="No transactions found in statement. Check bank format and file encoding.",
        )

    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    entity = (
        await session.execute(
            select(CpEntity).where(
                CpEntity.id == entity_id,
                CpEntity.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    stored = await store_bank_transactions(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        entity_name=entity.entity_name,
        bank_name=bank_name,
        transactions=transactions,
        uploaded_by=user.id,
    )

    await session.flush()
    return {
        "bank": bank_name,
        "transactions_parsed": len(transactions),
        "transactions_stored": len(stored),
        "date_range": {
            "from": min(t.transaction_date for t in transactions).isoformat(),
            "to": max(t.transaction_date for t in transactions).isoformat(),
        },
    }


@router.post("/statements", status_code=status.HTTP_201_CREATED)
async def create_statement(
    body: CreateStatementRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    resolved_entity_id = await resolve_entity_id(user.tenant_id, body.entity_id, session)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    entity = (
        await session.execute(
            select(CpEntity).where(
                CpEntity.id == resolved_entity_id,
                CpEntity.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    stmt = await create_bank_statement(
        session,
        tenant_id=user.tenant_id,
        bank_name=body.bank_name,
        account_number_masked=body.account_number_masked,
        currency=body.currency,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_id=resolved_entity_id,
        entity_name=body.entity_name or entity.entity_name,
        opening_balance=body.opening_balance,
        closing_balance=body.closing_balance,
        file_name=body.file_name,
        file_hash=body.file_hash,
        uploaded_by=user.id,
        transaction_count=body.transaction_count,
        location_id=body.location_id,
        cost_centre_id=body.cost_centre_id,
    )
    await session.flush()
    return {
        "statement_id": str(stmt.id),
        "bank_name": stmt.bank_name,
        "entity_id": str(stmt.entity_id),
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
    entity_id: UUID | None = None,
    entity_name: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    if entity_id is not None:
        await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    effective_skip = offset if offset is not None else skip
    stmts = await list_bank_statements(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        entity_name=entity_name,
        limit=limit,
        offset=effective_skip,
    )
    count_stmt = select(func.count()).select_from(BankStatement).where(BankStatement.tenant_id == user.tenant_id)
    if period_year is not None:
        count_stmt = count_stmt.where(BankStatement.period_year == period_year)
    if period_month is not None:
        count_stmt = count_stmt.where(BankStatement.period_month == period_month)
    if entity_id is not None:
        count_stmt = count_stmt.where(BankStatement.entity_id == entity_id)
    if entity_name:
        count_stmt = count_stmt.where(BankStatement.entity_name == entity_name)
    total = int((await session.execute(count_stmt)).scalar_one())
    serialized = [
        {
            "statement_id": str(s.id),
            "bank_name": s.bank_name,
            "entity_id": str(s.entity_id),
            "entity_name": s.entity_name,
            "period": f"{s.period_year}-{s.period_month:02d}",
            "closing_balance": str(s.closing_balance),
            "transaction_count": s.transaction_count,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
        }
        for s in stmts
    ]
    return {
        "items": serialized,
        "statements": serialized,
        "total": total,
        "skip": effective_skip,
        "offset": effective_skip,
        "limit": limit,
        "has_more": (effective_skip + len(serialized)) < total,
        "count": len(serialized),
    }


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def add_transaction(
    body: AddTransactionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    statement = (
        await session.execute(
            select(BankStatement).where(
                BankStatement.id == body.statement_id,
                BankStatement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Bank statement not found")

    resolved_entity_id = body.entity_id or statement.entity_id
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    txn = await add_bank_transaction(
        session,
        tenant_id=user.tenant_id,
        statement_id=body.statement_id,
        entity_id=resolved_entity_id,
        transaction_date=body.transaction_date,
        description=body.description,
        debit_amount=body.debit_amount,
        credit_amount=body.credit_amount,
        balance=body.balance,
        reference=body.reference,
    )
    await session.flush()
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
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    effective_skip = offset if offset is not None else skip
    statement = (
        await session.execute(
            select(BankStatement).where(
                BankStatement.id == statement_id,
                BankStatement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    await assert_entity_access(session, user.tenant_id, statement.entity_id, user.id, user.role)
    txns = await list_bank_transactions(
        session,
        tenant_id=user.tenant_id,
        statement_id=statement_id,
        entity_id=statement.entity_id,
        limit=limit,
        offset=effective_skip,
    )
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(BankTransaction)
                .where(
                    BankTransaction.tenant_id == user.tenant_id,
                    BankTransaction.statement_id == statement_id,
                    BankTransaction.entity_id == statement.entity_id,
                )
            )
        ).scalar_one()
    )
    serialized = [
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
    ]
    return {
        "items": serialized,
        "transactions": serialized,
        "total": total,
        "skip": effective_skip,
        "offset": effective_skip,
        "limit": limit,
        "has_more": (effective_skip + len(serialized)) < total,
        "count": len(serialized),
    }


@router.post("/run/{statement_id}", status_code=status.HTTP_201_CREATED)
async def run_bank_recon(
    statement_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    statement = (
        await session.execute(
            select(BankStatement).where(
                BankStatement.id == statement_id,
                BankStatement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    await assert_entity_access(session, user.tenant_id, statement.entity_id, user.id, user.role)
    items = await run_bank_reconciliation(
        session,
        tenant_id=user.tenant_id,
        statement_id=statement_id,
        run_by=user.id,
    )
    await session.flush()
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
    entity_id: UUID | None = None,
    statement_id: UUID | None = None,
    item_status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    if entity_id is not None:
        await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    effective_skip = offset if offset is not None else skip
    items = await list_bank_recon_items(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        statement_id=statement_id,
        status=item_status,
        limit=limit,
        offset=effective_skip,
    )
    count_stmt = select(func.count()).select_from(BankReconItem).where(BankReconItem.tenant_id == user.tenant_id)
    if entity_id is not None:
        count_stmt = count_stmt.where(BankReconItem.entity_id == entity_id)
    if statement_id is not None:
        count_stmt = count_stmt.where(BankReconItem.statement_id == statement_id)
    if item_status:
        count_stmt = count_stmt.where(BankReconItem.status == item_status)
    total = int((await session.execute(count_stmt)).scalar_one())
    serialized = [
        {
            "item_id": str(i.id),
            "item_type": i.item_type,
            "amount": str(i.amount),
            "status": i.status,
            "entity_id": str(i.entity_id),
            "entity_name": i.entity_name,
            "period": f"{i.period_year}-{i.period_month:02d}",
        }
        for i in items
    ]
    return {
        "items": serialized,
        "total": total,
        "skip": effective_skip,
        "offset": effective_skip,
        "limit": limit,
        "has_more": (effective_skip + len(serialized)) < total,
        "count": len(serialized),
    }
