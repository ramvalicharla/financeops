from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.core.governance.approvals import ApprovalPolicyResolver, ApprovalRequest
from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.core.governance.guards import GuardEngine, MutationGuardContext
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.gst import GstReconItem, GstReturn
from financeops.db.models.users import IamUser
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.services.context_resolver import resolve_entity_id
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.services.gst_service import (
    create_gst_return,
    list_gst_recon_items,
    list_gst_returns,
    run_gst_reconciliation,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _decimal_string(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." not in rendered:
        return rendered
    stripped = rendered.rstrip("0").rstrip(".")
    return stripped or "0"


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
    target_id: UUID | None = None,
):
    service = IntentService(session)
    return await service.submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        target_id=target_id,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
    )


class CreateGstReturnRequest(BaseModel):
    period_year: int
    period_month: int
    entity_id: UUID | None = None
    entity_name: str | None = None
    location_id: UUID | None = None
    cost_centre_id: UUID | None = None
    gstin: str
    return_type: str  # GSTR1 / GSTR3B / GSTR2A / GSTR2B
    taxable_value: Decimal
    igst_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    cess_amount: Decimal = Decimal("0")
    filing_date: date | None = None
    notes: str | None = None


class RunGstReconRequest(BaseModel):
    period_year: int
    period_month: int
    entity_id: UUID | None = None
    entity_name: str | None = None
    return_type_a: str
    return_type_b: str


class SubmitGstReturnRequest(BaseModel):
    filing_date: date | None = None


@router.post("/returns", status_code=status.HTTP_201_CREATED)
async def create_return(
    request: Request,
    body: CreateGstReturnRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Record a GST return (INSERT ONLY)."""
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
    resolved_entity_name = body.entity_name or entity.entity_name
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.PREPARE_GST_RETURN,
        payload={
            **body.model_dump(mode="json"),
            "entity_id": str(resolved_entity_id),
            "entity_name": resolved_entity_name,
        },
    )
    ret = (
        await session.execute(
            select(GstReturn).where(
                GstReturn.id == UUID(str((result.record_refs or {})["return_id"])),
                GstReturn.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    return {
        "return_id": str(ret.id),
        "return_type": ret.return_type,
        "period": f"{ret.period_year}-{ret.period_month:02d}",
        "entity_id": str(ret.entity_id),
        "entity_name": ret.entity_name,
        "gstin": ret.gstin,
        "total_tax": _decimal_string(ret.total_tax),
        "status": ret.status,
        "created_at": ret.created_at.isoformat(),
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.get("/returns")
async def list_returns(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_id: UUID | None = None,
    entity_name: str | None = None,
    return_type: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List GST returns."""
    if entity_id is not None:
        await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    effective_skip = offset if offset is not None else skip
    returns = await list_gst_returns(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        entity_name=entity_name,
        return_type=return_type,
        limit=limit,
        offset=effective_skip,
    )
    count_stmt = select(func.count()).select_from(GstReturn).where(GstReturn.tenant_id == user.tenant_id)
    if period_year is not None:
        count_stmt = count_stmt.where(GstReturn.period_year == period_year)
    if period_month is not None:
        count_stmt = count_stmt.where(GstReturn.period_month == period_month)
    if entity_id is not None:
        count_stmt = count_stmt.where(GstReturn.entity_id == entity_id)
    if entity_name:
        count_stmt = count_stmt.where(GstReturn.entity_name == entity_name)
    if return_type:
        count_stmt = count_stmt.where(GstReturn.return_type == return_type)
    total = int((await session.execute(count_stmt)).scalar_one())
    serialized = [
        {
            "return_id": str(r.id),
            "return_type": r.return_type,
            "period": f"{r.period_year}-{r.period_month:02d}",
            "entity_id": str(r.entity_id),
            "entity_name": r.entity_name,
            "gstin": r.gstin,
            "total_tax": _decimal_string(r.total_tax),
            "status": r.status,
        }
        for r in returns
    ]
    return {
        "items": serialized,
        "returns": serialized,
        "total": total,
        "skip": effective_skip,
        "offset": effective_skip,
        "limit": limit,
        "has_more": (effective_skip + len(serialized)) < total,
        "count": len(serialized),
    }


@router.get("/returns/{return_id}")
async def get_return(
    return_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(GstReturn).where(
                GstReturn.id == return_id,
                GstReturn.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="GST return not found")
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return {
        "return_id": str(row.id),
        "return_type": row.return_type,
        "period": f"{row.period_year}-{row.period_month:02d}",
        "entity_id": str(row.entity_id),
        "entity_name": row.entity_name,
        "gstin": row.gstin,
        "taxable_value": _decimal_string(row.taxable_value),
        "igst_amount": _decimal_string(row.igst_amount),
        "cgst_amount": _decimal_string(row.cgst_amount),
        "sgst_amount": _decimal_string(row.sgst_amount),
        "cess_amount": _decimal_string(row.cess_amount),
        "total_tax": _decimal_string(row.total_tax),
        "status": row.status,
        "filing_date": row.filing_date.isoformat() if row.filing_date else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/returns/{return_id}/submit")
async def submit_return(
    return_id: UUID,
    body: SubmitGstReturnRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    row = (
        await session.execute(
            select(GstReturn).where(
                GstReturn.id == return_id,
                GstReturn.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="GST return not found")
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.SUBMIT_GST_RETURN,
        payload={**body.model_dump(mode="json"), "entity_id": str(row.entity_id)},
        target_id=return_id,
    )
    submitted = (
        await session.execute(
            select(GstReturn).where(
                GstReturn.id == return_id,
                GstReturn.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    return {
        "return_id": str(submitted.id),
        "status": submitted.status,
        "filing_date": submitted.filing_date.isoformat() if submitted.filing_date else None,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.post("/reconcile", status_code=status.HTTP_201_CREATED)
async def run_gst_recon(
    request: Request,
    body: RunGstReconRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Run GST reconciliation between two return types for the same period."""
    resolved_entity_id = await resolve_entity_id(user.tenant_id, body.entity_id, session)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.RUN_GST_RECONCILIATION,
        payload={**body.model_dump(mode="json"), "entity_id": str(resolved_entity_id)},
    )
    item_ids = [UUID(str(value)) for value in ((result.record_refs or {}).get("item_ids") or [])]
    items = []
    if item_ids:
        items = list(
            (
                await session.execute(
                    select(GstReconItem).where(
                        GstReconItem.tenant_id == user.tenant_id,
                        GstReconItem.id.in_(item_ids),
                    )
                )
            ).scalars().all()
        )
    return {
        "period": f"{body.period_year}-{body.period_month:02d}",
        "entity_id": str(resolved_entity_id),
        "comparison": f"{body.return_type_a} vs {body.return_type_b}",
        "breaks_found": int((result.record_refs or {}).get("breaks_found") or len(items)),
        "items": [
            {
                "item_id": str(i.id),
                "field_name": i.field_name,
                "value_a": _decimal_string(i.value_a),
                "value_b": _decimal_string(i.value_b),
                "difference": _decimal_string(i.difference),
                "status": i.status,
            }
            for i in items
        ],
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.get("/recon-items")
async def list_gst_recon_items_endpoint(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_id: UUID | None = None,
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
    items = await list_gst_recon_items(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        status=item_status,
        limit=limit,
        offset=effective_skip,
    )
    count_stmt = select(func.count()).select_from(GstReconItem).where(GstReconItem.tenant_id == user.tenant_id)
    if period_year is not None:
        count_stmt = count_stmt.where(GstReconItem.period_year == period_year)
    if period_month is not None:
        count_stmt = count_stmt.where(GstReconItem.period_month == period_month)
    if entity_id is not None:
        count_stmt = count_stmt.where(GstReconItem.entity_id == entity_id)
    if item_status:
        count_stmt = count_stmt.where(GstReconItem.status == item_status)
    total = int((await session.execute(count_stmt)).scalar_one())
    serialized = [
        {
            "item_id": str(i.id),
            "field_name": i.field_name,
            "return_type_a": i.return_type_a,
            "return_type_b": i.return_type_b,
            "entity_id": str(i.entity_id),
            "value_a": str(i.value_a),
            "value_b": str(i.value_b),
            "difference": str(i.difference),
            "status": i.status,
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
