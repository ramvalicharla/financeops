from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


@router.post("/returns", status_code=status.HTTP_201_CREATED)
async def create_return(
    body: CreateGstReturnRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Record a GST return (INSERT ONLY)."""
    guard_engine = GuardEngine()
    approval_resolver = ApprovalPolicyResolver()
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
    actor = GovernanceActor(user_id=user.id, role=user.role.value)
    guard_result = await guard_engine.evaluate_mutation(
        session,
        context=MutationGuardContext(
            tenant_id=user.tenant_id,
            module_key="gst",
            mutation_type="GST_RETURN_SUBMIT",
            actor_user_id=user.id,
            actor_role=user.role.value,
            entity_id=resolved_entity_id,
            amount=body.taxable_value,
            subject_type="gst_return",
            subject_id=f"{resolved_entity_id}:{body.return_type}:{body.period_year}-{body.period_month:02d}",
        ),
    )
    if not guard_result.overall_passed:
        raise HTTPException(
            status_code=422,
            detail="; ".join(item.message for item in guard_result.blocking_failures),
        )
    approval = await approval_resolver.resolve_mutation(
        session,
        request=ApprovalRequest(
            tenant_id=user.tenant_id,
            module_key="gst",
            mutation_type="GST_RETURN_SUBMIT",
            entity_id=resolved_entity_id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            amount=body.taxable_value,
            subject_type="gst_return",
            subject_id=f"{resolved_entity_id}:{body.return_type}:{body.period_year}-{body.period_month:02d}",
        ),
    )
    if approval.approval_required and not approval.is_granted:
        raise HTTPException(status_code=422, detail=approval.reason)

    ret = await create_gst_return(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_id=resolved_entity_id,
        entity_name=resolved_entity_name,
        gstin=body.gstin,
        return_type=body.return_type,
        taxable_value=body.taxable_value,
        igst_amount=body.igst_amount,
        cgst_amount=body.cgst_amount,
        sgst_amount=body.sgst_amount,
        cess_amount=body.cess_amount,
        filing_date=body.filing_date,
        notes=body.notes,
        location_id=body.location_id,
        cost_centre_id=body.cost_centre_id,
        created_by=user.id,
    )
    await session.flush()
    await emit_governance_event(
        session,
        tenant_id=user.tenant_id,
        module_key="gst",
        subject_type="gst_return",
        subject_id=str(ret.id),
        event_type="RECORD_RECORDED",
        actor=actor,
        entity_id=resolved_entity_id,
        payload={
            "return_type": ret.return_type,
            "period": f"{ret.period_year}-{ret.period_month:02d}",
            "total_tax": str(ret.total_tax),
        },
    )
    return {
        "return_id": str(ret.id),
        "return_type": ret.return_type,
        "period": f"{ret.period_year}-{ret.period_month:02d}",
        "entity_id": str(ret.entity_id),
        "entity_name": ret.entity_name,
        "gstin": ret.gstin,
        "total_tax": str(ret.total_tax),
        "status": ret.status,
        "created_at": ret.created_at.isoformat(),
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
            "total_tax": str(r.total_tax),
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
        "taxable_value": str(row.taxable_value),
        "igst_amount": str(row.igst_amount),
        "cgst_amount": str(row.cgst_amount),
        "sgst_amount": str(row.sgst_amount),
        "cess_amount": str(row.cess_amount),
        "total_tax": str(row.total_tax),
        "status": row.status,
        "filing_date": row.filing_date.isoformat() if row.filing_date else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/reconcile", status_code=status.HTTP_201_CREATED)
async def run_gst_recon(
    body: RunGstReconRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Run GST reconciliation between two return types for the same period."""
    resolved_entity_id = await resolve_entity_id(user.tenant_id, body.entity_id, session)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    items = await run_gst_reconciliation(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_id=resolved_entity_id,
        return_type_a=body.return_type_a,
        return_type_b=body.return_type_b,
        run_by=user.id,
    )
    await session.flush()
    return {
        "period": f"{body.period_year}-{body.period_month:02d}",
        "entity_id": str(resolved_entity_id),
        "comparison": f"{body.return_type_a} vs {body.return_type_b}",
        "breaks_found": len(items),
        "items": [
            {
                "item_id": str(i.id),
                "field_name": i.field_name,
                "value_a": str(i.value_a),
                "value_b": str(i.value_b),
                "difference": str(i.difference),
                "status": i.status,
            }
            for i in items
        ],
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
