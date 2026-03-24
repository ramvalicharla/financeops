from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.marketplace.models import (
    MarketplaceContributor,
    MarketplacePayout,
    MarketplacePurchase,
    MarketplaceRating,
    MarketplaceTemplate,
)
from financeops.modules.marketplace.service import (
    get_contributor_dashboard,
    get_marketplace_listings,
    process_monthly_payouts,
    purchase_template,
    rate_template,
    register_contributor,
    review_template,
    submit_template,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class ContributorRegisterRequest(BaseModel):
    display_name: str
    bio: str | None = None


class TemplateSubmitRequest(BaseModel):
    title: str
    description: str
    template_type: str
    price_credits: int
    template_data: dict = Field(default_factory=dict)
    industry: str | None = None
    tags: list[str] = Field(default_factory=list)


class TemplateUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    template_type: str | None = None
    price_credits: int | None = None
    template_data: dict | None = None
    industry: str | None = None
    tags: list[str] | None = None


class ReviewTemplateRequest(BaseModel):
    action: str
    review_notes: str | None = None


class RateTemplateRequest(BaseModel):
    rating: int
    review_text: str | None = None


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _serialize_contributor(row: MarketplaceContributor) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "display_name": row.display_name,
        "bio": row.bio,
        "contributor_tier": row.contributor_tier,
        "revenue_share_pct": format(Decimal(str(row.revenue_share_pct)), "f"),
        "stripe_account_id": row.stripe_account_id,
        "total_earnings": format(Decimal(str(row.total_earnings)), "f"),
        "total_templates": row.total_templates,
        "total_downloads": row.total_downloads,
        "rating_average": format(Decimal(str(row.rating_average)), "f"),
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_template(row: MarketplaceTemplate, contributor: MarketplaceContributor | None = None) -> dict:
    payload = {
        "id": str(row.id),
        "contributor_id": str(row.contributor_id),
        "tenant_id": str(row.tenant_id),
        "title": row.title,
        "description": row.description,
        "template_type": row.template_type,
        "industry": row.industry,
        "price_credits": row.price_credits,
        "is_free": row.is_free,
        "template_data": row.template_data,
        "preview_image_url": row.preview_image_url,
        "tags": list(row.tags or []),
        "download_count": row.download_count,
        "rating_count": row.rating_count,
        "rating_sum": row.rating_sum,
        "rating_average": format(Decimal(str(row.rating_average)), "f"),
        "status": row.status,
        "review_notes": row.review_notes,
        "is_featured": row.is_featured,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
    if contributor is not None:
        payload["contributor"] = _serialize_contributor(contributor)
    return payload


def _serialize_purchase(row: MarketplacePurchase) -> dict:
    return {
        "id": str(row.id),
        "template_id": str(row.template_id),
        "buyer_tenant_id": str(row.buyer_tenant_id),
        "contributor_id": str(row.contributor_id),
        "price_credits_paid": row.price_credits_paid,
        "platform_share_credits": row.platform_share_credits,
        "contributor_share_credits": row.contributor_share_credits,
        "platform_share_pct": format(Decimal(str(row.platform_share_pct)), "f"),
        "contributor_share_pct": format(Decimal(str(row.contributor_share_pct)), "f"),
        "status": row.status,
        "purchased_at": row.purchased_at.isoformat(),
    }


def _serialize_rating(row: MarketplaceRating) -> dict:
    return {
        "id": str(row.id),
        "template_id": str(row.template_id),
        "buyer_tenant_id": str(row.buyer_tenant_id),
        "rating": row.rating,
        "review_text": row.review_text,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_payout(row: MarketplacePayout) -> dict:
    return {
        "id": str(row.id),
        "contributor_id": str(row.contributor_id),
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "total_credits_earned": row.total_credits_earned,
        "total_usd_amount": format(Decimal(str(row.total_usd_amount)), "f"),
        "status": row.status,
        "stripe_transfer_id": row.stripe_transfer_id,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        "created_at": row.created_at.isoformat(),
    }


async def _get_contributor_by_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> MarketplaceContributor | None:
    return (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


@router.get("/templates", response_model=Paginated[dict])
async def list_templates_endpoint(
    template_type: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    is_free: bool | None = Query(default=None),
    sort_by: str = Query(default="featured"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    del user
    payload = await get_marketplace_listings(
        session,
        template_type=template_type,
        industry=industry,
        is_free=is_free,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    rows = payload["data"]
    contributor_ids = [row.contributor_id for row in rows]
    contributors = (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.id.in_(contributor_ids))
        )
    ).scalars().all() if contributor_ids else []
    by_id = {row.id: row for row in contributors}
    return Paginated[dict](
        data=[_serialize_template(row, by_id.get(row.contributor_id)) for row in rows],
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
    )


@router.get("/templates/{template_id}")
async def get_template_endpoint(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    del user
    template = (
        await session.execute(select(MarketplaceTemplate).where(MarketplaceTemplate.id == template_id))
    ).scalar_one_or_none()
    if template is None or template.status != "published":
        raise HTTPException(status_code=404, detail="Template not found")
    contributor = (
        await session.execute(
            select(MarketplaceContributor).where(MarketplaceContributor.id == template.contributor_id)
        )
    ).scalar_one_or_none()
    ratings = (
        await session.execute(
            select(MarketplaceRating)
            .where(MarketplaceRating.template_id == template.id)
            .order_by(desc(MarketplaceRating.created_at), desc(MarketplaceRating.id))
            .limit(20)
        )
    ).scalars().all()
    return {
        "template": _serialize_template(template, contributor),
        "reviews": [_serialize_rating(row) for row in ratings],
    }


@router.post("/templates/{template_id}/purchase", status_code=status.HTTP_201_CREATED)
async def purchase_template_endpoint(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        purchase = await purchase_template(
            session,
            buyer_tenant_id=user.tenant_id,
            template_id=template_id,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=exc.message) from exc
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(getattr(exc, "message", str(exc)))) from exc
    template = (
        await session.execute(select(MarketplaceTemplate).where(MarketplaceTemplate.id == purchase.template_id))
    ).scalar_one()
    return {
        "purchase": _serialize_purchase(purchase),
        "template_data": template.template_data,
    }


@router.post("/templates/{template_id}/rate", status_code=status.HTTP_201_CREATED)
async def rate_template_endpoint(
    template_id: uuid.UUID,
    body: RateTemplateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        row = await rate_template(
            session,
            buyer_tenant_id=user.tenant_id,
            template_id=template_id,
            rating=body.rating,
            review_text=body.review_text,
        )
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(getattr(exc, "message", str(exc)))) from exc
    return _serialize_rating(row)


@router.post("/contributor/register", status_code=status.HTTP_201_CREATED)
async def register_contributor_endpoint(
    body: ContributorRegisterRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await register_contributor(
        session,
        tenant_id=user.tenant_id,
        display_name=body.display_name,
        bio=body.bio,
    )
    return _serialize_contributor(row)


@router.get("/contributor/dashboard")
async def contributor_dashboard_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    contributor = await _get_contributor_by_tenant(session, user.tenant_id)
    if contributor is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    payload = await get_contributor_dashboard(session, contributor.id)
    return {
        "contributor": _serialize_contributor(payload["contributor"]),
        "templates": [_serialize_template(row) for row in payload["templates"]],
        "earnings_this_month": format(payload["earnings_this_month"], "f"),
        "earnings_total": format(payload["earnings_total"], "f"),
        "top_template": (
            _serialize_template(payload["top_template"])
            if payload["top_template"] is not None
            else None
        ),
        "recent_purchases": [_serialize_purchase(row) for row in payload["recent_purchases"]],
        "payout_history": [_serialize_payout(row) for row in payload["payout_history"]],
    }


@router.post("/contributor/templates", status_code=status.HTTP_201_CREATED)
async def submit_template_endpoint(
    body: TemplateSubmitRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    contributor = await _get_contributor_by_tenant(session, user.tenant_id)
    if contributor is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    try:
        row = await submit_template(
            session,
            contributor_id=contributor.id,
            tenant_id=user.tenant_id,
            title=body.title,
            description=body.description,
            template_type=body.template_type,
            price_credits=body.price_credits,
            template_data=body.template_data,
            industry=body.industry,
            tags=body.tags,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _serialize_template(row)


@router.patch("/contributor/templates/{template_id}")
async def update_contributor_template_endpoint(
    template_id: uuid.UUID,
    body: TemplateUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    contributor = await _get_contributor_by_tenant(session, user.tenant_id)
    if contributor is None:
        raise HTTPException(status_code=404, detail="Contributor not found")

    row = (
        await session.execute(
            select(MarketplaceTemplate).where(
                MarketplaceTemplate.id == template_id,
                MarketplaceTemplate.contributor_id == contributor.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if row.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=422, detail="Only draft or rejected templates can be edited")

    if body.title is not None:
        row.title = body.title
    if body.description is not None:
        row.description = body.description
    if body.template_type is not None:
        row.template_type = body.template_type
    if body.price_credits is not None:
        if body.price_credits < 0:
            raise HTTPException(status_code=422, detail="price_credits must be >= 0")
        row.price_credits = body.price_credits
        row.is_free = body.price_credits == 0
    if body.template_data is not None:
        row.template_data = body.template_data
    if body.industry is not None:
        row.industry = body.industry
    if body.tags is not None:
        row.tags = list(body.tags)

    row.status = "pending_review"
    from datetime import UTC, datetime
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _serialize_template(row)


@router.get("/admin/pending")
async def admin_pending_templates_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    stmt: Select[tuple[MarketplaceTemplate]] = select(MarketplaceTemplate).where(
        MarketplaceTemplate.status == "pending_review"
    )
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(MarketplaceTemplate.created_at), desc(MarketplaceTemplate.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_template(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/admin/templates/{template_id}/review")
async def admin_review_template_endpoint(
    template_id: uuid.UUID,
    body: ReviewTemplateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    try:
        row = await review_template(
            session,
            template_id=template_id,
            action=body.action,
            review_notes=body.review_notes,
        )
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(getattr(exc, "message", str(exc)))) from exc
    return _serialize_template(row)


@router.post("/admin/payouts/process")
async def admin_process_payouts_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    rows = await process_monthly_payouts(session)
    return {"count": len(rows), "payouts": [_serialize_payout(row) for row in rows]}


@router.get("/admin/stats")
async def admin_marketplace_stats_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    total_templates = int((await session.execute(select(func.count()).select_from(MarketplaceTemplate))).scalar_one())
    published_templates = int(
        (
            await session.execute(
                select(func.count()).select_from(MarketplaceTemplate).where(MarketplaceTemplate.status == "published")
            )
        ).scalar_one()
    )
    total_revenue_credits = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(MarketplacePurchase.price_credits_paid), 0))
            )
        ).scalar_one()
    )
    top_contributors = (
        await session.execute(
            select(MarketplaceContributor)
            .order_by(desc(MarketplaceContributor.total_earnings), desc(MarketplaceContributor.id))
            .limit(5)
        )
    ).scalars().all()

    return {
        "total_templates": total_templates,
        "published_templates": published_templates,
        "total_revenue_credits": total_revenue_credits,
        "top_contributors": [_serialize_contributor(row) for row in top_contributors],
    }


__all__ = ["router"]
