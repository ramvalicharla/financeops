from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.modules.transfer_pricing.models import ICTransaction, TransferPricingDoc
from financeops.modules.transfer_pricing.service import (
    add_transaction,
    check_3ceb_applicability,
    generate_form_3ceb,
    list_documents,
    list_transactions,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/transfer-pricing", tags=["transfer_pricing"])


class AddTransactionRequest(BaseModel):
    fiscal_year: int
    transaction_type: str
    related_party_name: str
    related_party_country: str
    transaction_amount: Decimal
    currency: str = "INR"
    pricing_method: str
    is_international: bool = True
    arm_length_price: Decimal | None = None
    actual_price: Decimal | None = None
    description: str | None = None


class Generate3CEBRequest(BaseModel):
    fiscal_year: int


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_txn(row: ICTransaction) -> dict:
    return {
        "id": str(row.id),
        "fiscal_year": row.fiscal_year,
        "transaction_type": row.transaction_type,
        "related_party_name": row.related_party_name,
        "related_party_country": row.related_party_country,
        "transaction_amount": _decimal(row.transaction_amount),
        "currency": row.currency,
        "transaction_amount_inr": _decimal(row.transaction_amount_inr),
        "pricing_method": row.pricing_method,
        "arm_length_price": _decimal(row.arm_length_price) if row.arm_length_price is not None else None,
        "actual_price": _decimal(row.actual_price) if row.actual_price is not None else None,
        "adjustment_required": _decimal(row.adjustment_required),
        "is_international": row.is_international,
        "description": row.description,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_doc(row: TransferPricingDoc) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "fiscal_year": row.fiscal_year,
        "document_type": row.document_type,
        "version": row.version,
        "content": row.content,
        "ai_narrative": row.ai_narrative,
        "status": row.status,
        "filed_at": row.filed_at.isoformat() if row.filed_at else None,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


@router.get("/applicability")
async def applicability_endpoint(
    fiscal_year: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    fy = fiscal_year or datetime.utcnow().year
    payload = await check_3ceb_applicability(session, tenant_id=user.tenant_id, fiscal_year=fy)
    return {
        "is_required": payload["is_required"],
        "reason": payload["reason"],
        "international_transaction_value": _decimal(payload["international_transaction_value"]),
        "domestic_transaction_value": _decimal(payload["domestic_transaction_value"]),
    }


@router.post("/transactions")
async def add_transaction_endpoint(
    body: AddTransactionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await add_transaction(
        session,
        tenant_id=user.tenant_id,
        fiscal_year=body.fiscal_year,
        transaction_type=body.transaction_type,
        related_party_name=body.related_party_name,
        related_party_country=body.related_party_country,
        transaction_amount=body.transaction_amount,
        currency=body.currency,
        pricing_method=body.pricing_method,
        is_international=body.is_international,
        arm_length_price=body.arm_length_price,
        actual_price=body.actual_price,
        description=body.description,
    )
    return _serialize_txn(row)


@router.get("/transactions", response_model=Paginated[dict])
async def list_transactions_endpoint(
    fiscal_year: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    payload = await list_transactions(session, tenant_id=user.tenant_id, fiscal_year=fiscal_year, limit=limit, offset=offset)
    return Paginated[dict](data=[_serialize_txn(row) for row in payload["data"]], total=payload["total"], limit=payload["limit"], offset=payload["offset"])


@router.post("/generate-3ceb")
async def generate_3ceb_endpoint(
    body: Generate3CEBRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await generate_form_3ceb(session, tenant_id=user.tenant_id, fiscal_year=body.fiscal_year, created_by=user.id)
    return _serialize_doc(row)


@router.get("/documents", response_model=Paginated[dict])
async def list_documents_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    payload = await list_documents(session, tenant_id=user.tenant_id, limit=limit, offset=offset)
    return Paginated[dict](data=[_serialize_doc(row) for row in payload["data"]], total=payload["total"], limit=payload["limit"], offset=payload["offset"])


@router.get("/documents/{document_id}")
async def get_document_endpoint(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(TransferPricingDoc).where(TransferPricingDoc.id == document_id, TransferPricingDoc.tenant_id == user.tenant_id)
        )
    ).scalar_one()
    return _serialize_doc(row)


__all__ = ["router"]
