from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.statutory.models import StatutoryFiling, StatutoryRegisterEntry
from financeops.modules.statutory.service import add_register_entry, get_compliance_calendar, get_register, list_filings, mark_as_filed
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/statutory", tags=["statutory"])


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
):
    return await IntentService(session).submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
        ),
    )


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
        "entity_id": str(row.entity_id),
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
        "entity_id": str(row.entity_id),
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


async def _resolve_entity_id(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if entities:
        return entities[0].id
    raise HTTPException(status_code=422, detail="entity_id is required because no entity is configured for this user")


@router.get("/calendar")
async def calendar_endpoint(
    request: Request,
    fiscal_year: int,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    existing_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(StatutoryFiling)
                .where(
                    StatutoryFiling.tenant_id == user.tenant_id,
                    StatutoryFiling.entity_id == resolved_entity_id,
                    StatutoryFiling.due_date >= date(fiscal_year, 1, 1),
                    StatutoryFiling.due_date <= date(fiscal_year, 12, 31),
                )
            )
        ).scalar_one()
    )
    if existing_count == 0:
        await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.ENSURE_STATUTORY_FILINGS,
            payload={"entity_id": str(resolved_entity_id), "fiscal_year": fiscal_year},
        )
    rows = await get_compliance_calendar(
        session,
        tenant_id=user.tenant_id,
        fiscal_year=fiscal_year,
        entity_id=resolved_entity_id,
    )
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
    entity_id: uuid.UUID | None = None,
    status: str | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    effective_skip = offset if offset is not None else skip
    payload = await list_filings(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
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
    request: Request,
    filing_id: uuid.UUID,
    body: MarkFiledRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    except HTTPException as exc:
        if exc.status_code == 422:
            raise HTTPException(status_code=404, detail="Filing not found") from exc
        raise
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.MARK_STATUTORY_FILING,
        payload={
            "filing_id": str(filing_id),
            "filed_date": body.filed_date.isoformat(),
            "filing_reference": body.filing_reference,
            "entity_id": str(resolved_entity_id),
        },
    )
    row = (
        await session.execute(
            select(StatutoryFiling).where(
                StatutoryFiling.id == uuid.UUID(str((result.record_refs or {})["filing_id"])),
                StatutoryFiling.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    payload = _serialize_filing(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


@router.get("/registers/{register_type}", response_model=Paginated[dict])
async def register_endpoint(
    register_type: str,
    entity_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    effective_skip = offset if offset is not None else skip
    payload = await get_register(
        session,
        tenant_id=user.tenant_id,
        register_type=register_type,
        entity_id=resolved_entity_id,
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
    request: Request,
    register_type: str,
    body: AddRegisterEntryRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.ADD_STATUTORY_REGISTER_ENTRY,
        payload={
            "register_type": register_type,
            "entry_date": body.entry_date.isoformat(),
            "entry_description": body.entry_description,
            "entity_id": str(resolved_entity_id),
            "folio_number": body.folio_number,
            "amount": str(body.amount) if body.amount is not None else None,
            "currency": body.currency,
            "reference_document": body.reference_document,
        },
    )
    row = (
        await session.execute(
            select(StatutoryRegisterEntry).where(
                StatutoryRegisterEntry.id == uuid.UUID(str((result.record_refs or {})["entry_id"])),
                StatutoryRegisterEntry.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    payload = _serialize_register(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


__all__ = ["router"]
