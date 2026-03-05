from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.db.models.users import IamUser
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
    entity_name: str
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
    entity_name: str
    return_type_a: str
    return_type_b: str


@router.post("/returns", status_code=status.HTTP_201_CREATED)
async def create_return(
    body: CreateGstReturnRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Record a GST return (INSERT ONLY)."""
    ret = await create_gst_return(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        gstin=body.gstin,
        return_type=body.return_type,
        taxable_value=body.taxable_value,
        igst_amount=body.igst_amount,
        cgst_amount=body.cgst_amount,
        sgst_amount=body.sgst_amount,
        cess_amount=body.cess_amount,
        filing_date=body.filing_date,
        notes=body.notes,
        created_by=user.id,
    )
    await session.commit()
    return {
        "return_id": str(ret.id),
        "return_type": ret.return_type,
        "period": f"{ret.period_year}-{ret.period_month:02d}",
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
    entity_name: str | None = None,
    return_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List GST returns."""
    returns = await list_gst_returns(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        return_type=return_type,
        limit=limit,
        offset=offset,
    )
    return {
        "returns": [
            {
                "return_id": str(r.id),
                "return_type": r.return_type,
                "period": f"{r.period_year}-{r.period_month:02d}",
                "entity_name": r.entity_name,
                "gstin": r.gstin,
                "total_tax": str(r.total_tax),
                "status": r.status,
            }
            for r in returns
        ],
        "count": len(returns),
    }


@router.post("/reconcile", status_code=status.HTTP_201_CREATED)
async def run_gst_recon(
    body: RunGstReconRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Run GST reconciliation between two return types for the same period."""
    items = await run_gst_reconciliation(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        return_type_a=body.return_type_a,
        return_type_b=body.return_type_b,
        run_by=user.id,
    )
    await session.commit()
    return {
        "period": f"{body.period_year}-{body.period_month:02d}",
        "entity_name": body.entity_name,
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
    item_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    items = await list_gst_recon_items(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        status=item_status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "item_id": str(i.id),
                "field_name": i.field_name,
                "return_type_a": i.return_type_a,
                "return_type_b": i.return_type_b,
                "value_a": str(i.value_a),
                "value_b": str(i.value_b),
                "difference": str(i.difference),
                "status": i.status,
                "period": f"{i.period_year}-{i.period_month:02d}",
            }
            for i in items
        ],
        "count": len(items),
    }
