from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.statutory.models import StatutoryFiling, StatutoryRegisterEntry
from financeops.modules.statutory.service import add_register_entry, get_compliance_calendar, get_register, list_filings, mark_as_filed
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/statutory", tags=["statutory"])


class MarkFiledRequest(BaseModel):
    filed_date: date
    filing_reference: str


class AddRegisterEntryRequest(BaseModel):
    entry_date: date
    entry_description: str
    folio_number: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    reference_document: str | None = None


def _decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def _serialize_filing(row: StatutoryFiling) -> dict:
    return {
        "id": str(row.id),
        "form_number": row.form_number,
        "form_description": row.form_description,
        "due_date": row.due_date.isoformat(),
        "filed_date": row.filed_date.isoformat() if row.filed_date else None,
        "status": row.status,
        "filing_reference": row.filing_reference,
        "penalty_amount": _decimal(row.penalty_amount),
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_register(row: StatutoryRegisterEntry) -> dict:
    return {
        "id": str(row.id),
        "register_type": row.register_type,
        "entry_date": row.entry_date.isoformat(),
        "entry_description": row.entry_description,
        "folio_number": row.folio_number,
        "amount": _decimal(row.amount),
        "currency": row.currency,
        "reference_document": row.reference_document,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.get("/calendar")
async def calendar_endpoint(
    fiscal_year: int,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await get_compliance_calendar(session, tenant_id=user.tenant_id, fiscal_year=fiscal_year)
    return [
        {
            "id": row["id"],
            "form_number": row["form_number"],
            "form_description": row["form_description"],
            "due_date": row["due_date"].isoformat(),
            "filed_date": row["filed_date"].isoformat() if row["filed_date"] else None,
            "status": row["status"],
            "days_until_due": row["days_until_due"],
            "is_overdue": row["is_overdue"],
        }
        for row in rows
    ]


@router.get("/filings", response_model=Paginated[dict])
async def filings_endpoint(
    status: str | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    effective_skip = offset if offset is not None else skip
    payload = await list_filings(
        session,
        tenant_id=user.tenant_id,
        status=status,
        fiscal_year=fiscal_year,
        limit=limit,
        offset=effective_skip,
    )
    rows = [_serialize_filing(row) for row in payload["data"]]
    return Paginated[dict](
        items=rows,
        total=payload["total"],
        limit=payload["limit"],
        skip=effective_skip,
        has_more=(effective_skip + len(rows)) < int(payload["total"]),
    )


@router.post("/filings/{filing_id}/file")
async def mark_filed_endpoint(
    filing_id: uuid.UUID,
    body: MarkFiledRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await mark_as_filed(session, tenant_id=user.tenant_id, filing_id=filing_id, filed_date=body.filed_date, filing_reference=body.filing_reference)
    return _serialize_filing(row)


@router.get("/registers/{register_type}", response_model=Paginated[dict])
async def register_endpoint(
    register_type: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    effective_skip = offset if offset is not None else skip
    payload = await get_register(
        session,
        tenant_id=user.tenant_id,
        register_type=register_type,
        limit=limit,
        offset=effective_skip,
    )
    rows = [_serialize_register(row) for row in payload["data"]]
    return Paginated[dict](
        items=rows,
        total=payload["total"],
        limit=payload["limit"],
        skip=effective_skip,
        has_more=(effective_skip + len(rows)) < int(payload["total"]),
    )


@router.post("/registers/{register_type}")
async def add_register_endpoint(
    register_type: str,
    body: AddRegisterEntryRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await add_register_entry(
        session,
        tenant_id=user.tenant_id,
        register_type=register_type,
        entry_date=body.entry_date,
        entry_description=body.entry_description,
        folio_number=body.folio_number,
        amount=body.amount,
        currency=body.currency,
        reference_document=body.reference_document,
    )
    return _serialize_register(row)


__all__ = ["router"]
