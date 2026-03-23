from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.core.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.ppa.models import PPAAllocation, PPAEngagement, PPAIntangible
from financeops.modules.ppa.service import (
    create_ppa_engagement,
    export_ppa_report,
    get_ppa_report,
    identify_intangibles,
    run_ppa,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/advisory/ppa", tags=["advisory-ppa"])


class CreatePPARequest(BaseModel):
    engagement_name: str
    target_company_name: str
    acquisition_date: date
    purchase_price: str
    purchase_price_currency: str = "INR"
    accounting_standard: str


class IntangibleInput(BaseModel):
    name: str
    category: str
    valuation_method: str
    useful_life_years: str
    assumptions: dict[str, str] = Field(default_factory=dict)
    amortisation_method: str = "straight_line"
    tax_basis: str | None = None
    applicable_tax_rate: str | None = None


class RunPPARequest(BaseModel):
    intangibles: list[IntangibleInput]


def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a decimal string") from exc


def _serialize_engagement(row: PPAEngagement) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "engagement_name": row.engagement_name,
        "target_company_name": row.target_company_name,
        "acquisition_date": row.acquisition_date.isoformat(),
        "purchase_price": format(Decimal(str(row.purchase_price)), "f"),
        "purchase_price_currency": row.purchase_price_currency,
        "accounting_standard": row.accounting_standard,
        "status": row.status,
        "credit_cost": row.credit_cost,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_allocation(row: PPAAllocation) -> dict:
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "tenant_id": str(row.tenant_id),
        "allocation_version": row.allocation_version,
        "net_identifiable_assets": format(Decimal(str(row.net_identifiable_assets)), "f"),
        "total_intangibles_identified": format(Decimal(str(row.total_intangibles_identified)), "f"),
        "goodwill": format(Decimal(str(row.goodwill)), "f"),
        "deferred_tax_liability": format(Decimal(str(row.deferred_tax_liability)), "f"),
        "purchase_price_reconciliation": row.purchase_price_reconciliation,
        "computed_at": row.computed_at.isoformat(),
    }


def _serialize_intangible(row: PPAIntangible) -> dict:
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "allocation_id": str(row.allocation_id),
        "tenant_id": str(row.tenant_id),
        "intangible_name": row.intangible_name,
        "intangible_category": row.intangible_category,
        "fair_value": format(Decimal(str(row.fair_value)), "f"),
        "useful_life_years": format(Decimal(str(row.useful_life_years)), "f"),
        "amortisation_method": row.amortisation_method,
        "annual_amortisation": format(Decimal(str(row.annual_amortisation)), "f"),
        "tax_basis": format(Decimal(str(row.tax_basis)), "f"),
        "deferred_tax_liability": format(Decimal(str(row.deferred_tax_liability)), "f"),
        "valuation_method": row.valuation_method,
        "valuation_assumptions": row.valuation_assumptions,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/engagements", status_code=status.HTTP_201_CREATED)
async def create_engagement_endpoint(
    body: CreatePPARequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        engagement = await create_ppa_engagement(
            session,
            tenant_id=user.tenant_id,
            engagement_name=body.engagement_name,
            target_company_name=body.target_company_name,
            acquisition_date=body.acquisition_date,
            purchase_price=_to_decimal(body.purchase_price, "purchase_price"),
            purchase_price_currency=body.purchase_price_currency,
            accounting_standard=body.accounting_standard,
            created_by=user.id,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    await session.flush()
    return _serialize_engagement(engagement)


@router.get("/engagements")
async def list_engagements_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    stmt = select(PPAEngagement).where(PPAEngagement.tenant_id == user.tenant_id)
    if status_filter:
        stmt = stmt.where(PPAEngagement.status == status_filter)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(PPAEngagement.created_at.desc(), PPAEngagement.id.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_engagement(row) for row in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/engagements/{engagement_id}")
async def get_engagement_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    engagement = (
        await session.execute(
            select(PPAEngagement).where(
                PPAEngagement.id == engagement_id,
                PPAEngagement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=404, detail="PPA engagement not found")

    allocation = (
        await session.execute(
            select(PPAAllocation)
            .where(
                PPAAllocation.tenant_id == user.tenant_id,
                PPAAllocation.engagement_id == engagement_id,
            )
            .order_by(PPAAllocation.computed_at.desc(), PPAAllocation.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    intangibles = (
        await session.execute(
            select(PPAIntangible)
            .where(
                PPAIntangible.tenant_id == user.tenant_id,
                PPAIntangible.engagement_id == engagement_id,
            )
            .order_by(PPAIntangible.fair_value.desc(), PPAIntangible.id.desc())
        )
    ).scalars().all()

    return {
        "engagement": _serialize_engagement(engagement),
        "allocation": _serialize_allocation(allocation) if allocation is not None else None,
        "intangibles": [_serialize_intangible(row) for row in intangibles],
    }


@router.post("/engagements/{engagement_id}/identify-intangibles")
async def identify_intangibles_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    engagement = (
        await session.execute(
            select(PPAEngagement).where(
                PPAEngagement.id == engagement_id,
                PPAEngagement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=404, detail="PPA engagement not found")
    rows = await identify_intangibles(session, engagement)
    return {
        "intangibles": [
            {
                **item,
                "typical_useful_life_years": format(Decimal(str(item["typical_useful_life_years"])), "f"),
            }
            for item in rows
        ]
    }


@router.post("/engagements/{engagement_id}/run")
async def run_ppa_endpoint(
    engagement_id: uuid.UUID,
    body: RunPPARequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        allocation = await run_ppa(
            session,
            tenant_id=user.tenant_id,
            engagement_id=engagement_id,
            intangibles_input=[item.model_dump() for item in body.intangibles],
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    await session.flush()
    return _serialize_allocation(allocation)


@router.get("/engagements/{engagement_id}/report")
async def report_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        report = await get_ppa_report(session, user.tenant_id, engagement_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    return {
        "engagement": _serialize_engagement(report["engagement"]),
        "allocation": _serialize_allocation(report["allocation"]),
        "intangibles": [_serialize_intangible(row) for row in report["intangibles"]],
        "purchase_price_bridge": {
            "book_value_net_assets": format(Decimal(str(report["purchase_price_bridge"]["book_value_net_assets"])), "f"),
            "step_ups": [
                {
                    "name": row["name"],
                    "fair_value": format(Decimal(str(row["fair_value"])), "f"),
                    "tax_impact": format(Decimal(str(row["tax_impact"])), "f"),
                }
                for row in report["purchase_price_bridge"]["step_ups"]
            ],
            "goodwill": format(Decimal(str(report["purchase_price_bridge"]["goodwill"])), "f"),
            "total": format(Decimal(str(report["purchase_price_bridge"]["total"])), "f"),
        },
        "amortisation_schedule": {
            key: format(Decimal(str(value)), "f")
            for key, value in report["amortisation_schedule"].items()
        },
        "goodwill_pct_of_purchase_price": format(Decimal(str(report["goodwill_pct_of_purchase_price"])), "f"),
    }


@router.get("/engagements/{engagement_id}/export")
async def export_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Response:
    try:
        body = await export_ppa_report(session, user.tenant_id, engagement_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="PPA_Report_{engagement_id}.xlsx"'},
    )


__all__ = ["router"]
