from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.core.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.fdd.models import FDDEngagement, FDDFinding, FDDSection
from financeops.modules.fdd.service import (
    create_engagement,
    export_fdd_report,
    get_engagement_report,
)
from financeops.modules.fdd.tasks import run_fdd_engagement_task
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/advisory/fdd", tags=["advisory-fdd"])


class CreateFDDEngagementRequest(BaseModel):
    engagement_name: str
    target_company_name: str
    analysis_period_start: date
    analysis_period_end: date
    sections_requested: list[str] = Field(default_factory=list)


def _serialize_engagement(row: FDDEngagement) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "engagement_name": row.engagement_name,
        "target_company_name": row.target_company_name,
        "analysis_period_start": row.analysis_period_start.isoformat(),
        "analysis_period_end": row.analysis_period_end.isoformat(),
        "status": row.status,
        "credit_cost": row.credit_cost,
        "credits_reserved_at": row.credits_reserved_at.isoformat() if row.credits_reserved_at else None,
        "credits_deducted_at": row.credits_deducted_at.isoformat() if row.credits_deducted_at else None,
        "sections_requested": list(row.sections_requested or []),
        "sections_completed": list(row.sections_completed or []),
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_section(row: FDDSection) -> dict:
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "tenant_id": str(row.tenant_id),
        "section_name": row.section_name,
        "status": row.status,
        "result_data": row.result_data,
        "ai_narrative": row.ai_narrative,
        "computed_at": row.computed_at.isoformat(),
        "duration_seconds": format(Decimal(str(row.duration_seconds)), "f") if row.duration_seconds is not None else None,
    }


def _serialize_finding(row: FDDFinding) -> dict:
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "section_id": str(row.section_id),
        "tenant_id": str(row.tenant_id),
        "finding_type": row.finding_type,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "financial_impact": format(Decimal(str(row.financial_impact)), "f") if row.financial_impact is not None else None,
        "financial_impact_currency": row.financial_impact_currency,
        "recommended_action": row.recommended_action,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/engagements", status_code=status.HTTP_201_CREATED)
async def create_engagement_endpoint(
    body: CreateFDDEngagementRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        engagement = await create_engagement(
            session,
            tenant_id=user.tenant_id,
            engagement_name=body.engagement_name,
            target_company_name=body.target_company_name,
            analysis_period_start=body.analysis_period_start,
            analysis_period_end=body.analysis_period_end,
            sections_requested=body.sections_requested,
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
    stmt = select(FDDEngagement).where(FDDEngagement.tenant_id == user.tenant_id)
    if status_filter:
        stmt = stmt.where(FDDEngagement.status == status_filter)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(FDDEngagement.created_at.desc(), FDDEngagement.id.desc())
            .limit(limit)
            .offset(offset)
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
            select(FDDEngagement).where(
                FDDEngagement.id == engagement_id,
                FDDEngagement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=404, detail="FDD engagement not found")

    sections = (
        await session.execute(
            select(FDDSection)
            .where(
                FDDSection.tenant_id == user.tenant_id,
                FDDSection.engagement_id == engagement_id,
            )
            .order_by(FDDSection.computed_at.desc(), FDDSection.id.desc())
        )
    ).scalars().all()

    severity_rank = case(
        (FDDFinding.severity == "critical", 1),
        (FDDFinding.severity == "high", 2),
        (FDDFinding.severity == "medium", 3),
        (FDDFinding.severity == "low", 4),
        else_=5,
    )
    findings = (
        await session.execute(
            select(FDDFinding)
            .where(
                FDDFinding.tenant_id == user.tenant_id,
                FDDFinding.engagement_id == engagement_id,
            )
            .order_by(severity_rank.asc(), FDDFinding.created_at.asc())
        )
    ).scalars().all()

    return {
        "engagement": _serialize_engagement(engagement),
        "sections": [_serialize_section(row) for row in sections],
        "findings": [_serialize_finding(row) for row in findings],
    }


@router.post("/engagements/{engagement_id}/run")
async def run_engagement_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    engagement = (
        await session.execute(
            select(FDDEngagement).where(
                FDDEngagement.id == engagement_id,
                FDDEngagement.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=404, detail="FDD engagement not found")

    engagement.status = "running"
    await session.flush()

    try:
        async_result = JobDispatcher().enqueue_task(
            run_fdd_engagement_task,
            str(user.tenant_id),
            str(engagement_id),
        )
        task_id = str(getattr(async_result, "id", "")) or str(uuid.uuid4())
    except Exception:  # noqa: BLE001
        task_id = str(uuid.uuid4())

    return {"task_id": task_id, "status": "running"}


@router.get("/engagements/{engagement_id}/report")
async def report_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        report = await get_engagement_report(
            session,
            tenant_id=user.tenant_id,
            engagement_id=engagement_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    return {
        "engagement": _serialize_engagement(report["engagement"]),
        "sections": report["sections"],
        "findings": [_serialize_finding(item) for item in report["findings"]],
        "executive_summary": report["executive_summary"],
        "total_ebitda_adjustments": format(report["total_ebitda_adjustments"], "f"),
        "net_debt": format(report["net_debt"], "f"),
        "recommended_price_adjustments": format(report["recommended_price_adjustments"], "f"),
        "ltm_adjusted_ebitda": format(report["ltm_adjusted_ebitda"], "f"),
    }


@router.get("/engagements/{engagement_id}/export")
async def export_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Response:
    try:
        body = await export_fdd_report(
            session,
            tenant_id=user.tenant_id,
            engagement_id=engagement_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="FDD_Report_{engagement_id}.xlsx"'},
    )


__all__ = ["router"]
