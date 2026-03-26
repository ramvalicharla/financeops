from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import limiter
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.partner_program.models import PartnerCommission, PartnerProfile, ReferralTracking
from financeops.modules.partner_program.service import (
    approve_partner,
    get_partner_dashboard,
    register_partner,
    track_referral_click,
    track_referral_click_public,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/partner", tags=["partner-program"])


class RegisterPartnerRequest(BaseModel):
    partner_tier: str
    company_name: str
    contact_email: str
    website_url: str | None = None


class TrackReferralRequest(BaseModel):
    partner_code: str
    referral_email: str | None = None


def _require_partner_role(user: IamUser) -> IamUser:
    allowed = {
        "partner",
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
    }
    if user.role.value not in allowed:
        raise HTTPException(status_code=403, detail="partner role required")
    return user


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _serialize_partner(row: PartnerProfile) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "partner_tier": row.partner_tier,
        "company_name": row.company_name,
        "contact_email": row.contact_email,
        "website_url": row.website_url,
        "partner_code": row.partner_code,
        "commission_rate_pct": format(Decimal(str(row.commission_rate_pct)), "f"),
        "total_referrals": row.total_referrals,
        "total_commissions_earned": format(Decimal(str(row.total_commissions_earned)), "f"),
        "stripe_account_id": row.stripe_account_id,
        "is_active": row.is_active,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_referral(row: ReferralTracking) -> dict:
    return {
        "id": str(row.id),
        "partner_id": str(row.partner_id),
        "referred_tenant_id": str(row.referred_tenant_id) if row.referred_tenant_id else None,
        "tenant_id": str(row.tenant_id),
        "referral_code": row.referral_code,
        "referral_email": row.referral_email,
        "status": row.status,
        "clicked_at": row.clicked_at.isoformat(),
        "signed_up_at": row.signed_up_at.isoformat() if row.signed_up_at else None,
        "converted_at": row.converted_at.isoformat() if row.converted_at else None,
        "first_payment_amount": format(Decimal(str(row.first_payment_amount)), "f") if row.first_payment_amount is not None else None,
        "expires_at": row.expires_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_commission(row: PartnerCommission) -> dict:
    return {
        "id": str(row.id),
        "partner_id": str(row.partner_id),
        "referral_id": str(row.referral_id),
        "referred_tenant_id": str(row.referred_tenant_id),
        "commission_type": row.commission_type,
        "payment_amount": format(Decimal(str(row.payment_amount)), "f"),
        "commission_rate": format(Decimal(str(row.commission_rate)), "f"),
        "commission_amount": format(Decimal(str(row.commission_amount)), "f"),
        "status": row.status,
        "period": row.period,
        "created_at": row.created_at.isoformat(),
    }


async def _partner_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> PartnerProfile | None:
    return (
        await session.execute(
            select(PartnerProfile).where(PartnerProfile.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_partner_endpoint(
    body: RegisterPartnerRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        row = await register_partner(
            session,
            tenant_id=user.tenant_id,
            partner_tier=body.partner_tier,
            company_name=body.company_name,
            contact_email=body.contact_email,
            website_url=body.website_url,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _serialize_partner(row)


@limiter.limit("60/minute")
@router.get("/dashboard")
async def dashboard_endpoint(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    del request
    _require_partner_role(user)
    response.headers["X-RateLimit-Limit"] = "60/minute"
    partner = await _partner_for_tenant(session, user.tenant_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    payload = await get_partner_dashboard(session, partner.id)
    return {
        "partner": _serialize_partner(payload["partner"]),
        "referral_link": payload["referral_link"],
        "stats": {
            **payload["stats"],
            "conversion_rate": format(payload["stats"]["conversion_rate"], "f"),
            "total_commissions_earned": format(payload["stats"]["total_commissions_earned"], "f"),
            "pending_commissions": format(payload["stats"]["pending_commissions"], "f"),
        },
        "recent_referrals": [_serialize_referral(row) for row in payload["recent_referrals"]],
        "commission_history": [_serialize_commission(row) for row in payload["commission_history"]],
    }


@limiter.limit("60/minute")
@router.get("/referrals", response_model=Paginated[dict])
async def referrals_endpoint(
    request: Request,
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    del request
    _require_partner_role(user)
    response.headers["X-RateLimit-Limit"] = "60/minute"
    effective_skip = offset if offset is not None else skip
    partner = await _partner_for_tenant(session, user.tenant_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    stmt = select(ReferralTracking).where(ReferralTracking.partner_id == partner.id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(ReferralTracking.clicked_at), desc(ReferralTracking.id))
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    items = [_serialize_referral(row) for row in rows]
    return Paginated[dict](
        items=items,
        total=total,
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(items)) < total,
    )


@limiter.limit("60/minute")
@router.get("/commissions", response_model=Paginated[dict])
async def commissions_endpoint(
    request: Request,
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    del request
    _require_partner_role(user)
    response.headers["X-RateLimit-Limit"] = "60/minute"
    effective_skip = offset if offset is not None else skip
    partner = await _partner_for_tenant(session, user.tenant_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    stmt = select(PartnerCommission).where(PartnerCommission.partner_id == partner.id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(PartnerCommission.created_at), desc(PartnerCommission.id))
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    items = [_serialize_commission(row) for row in rows]
    return Paginated[dict](
        items=items,
        total=total,
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(items)) < total,
    )


@limiter.limit("60/minute")
@router.get("/payouts", response_model=Paginated[dict])
async def payouts_endpoint(
    request: Request,
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    del request
    _require_partner_role(user)
    response.headers["X-RateLimit-Limit"] = "60/minute"
    effective_skip = offset if offset is not None else skip
    partner = await _partner_for_tenant(session, user.tenant_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    stmt = select(PartnerCommission).where(
        PartnerCommission.partner_id == partner.id,
        PartnerCommission.status == "paid",
    )
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(PartnerCommission.created_at), desc(PartnerCommission.id))
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    items = [_serialize_commission(row) for row in rows]
    return Paginated[dict](
        items=items,
        total=total,
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(items)) < total,
    )


@router.post("/track")
async def track_referral_endpoint(body: TrackReferralRequest) -> dict:
    try:
        row = await track_referral_click_public(
            partner_code=body.partner_code,
            referral_email=body.referral_email,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return {"tracked": True, "referral_code": row.referral_code}


@router.get("/admin/applications", response_model=Paginated[dict])
async def admin_applications_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    stmt = select(PartnerProfile).where(PartnerProfile.approved_at.is_(None))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(PartnerProfile.created_at), desc(PartnerProfile.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_partner(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/admin/{partner_id}/approve")
async def admin_approve_partner_endpoint(
    partner_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    try:
        row = await approve_partner(session, partner_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return _serialize_partner(row)


@router.get("/admin/stats")
async def admin_partner_stats_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    total_partners = int((await session.execute(select(func.count()).select_from(PartnerProfile))).scalar_one())
    pending_applications = int(
        (
            await session.execute(
                select(func.count()).select_from(PartnerProfile).where(PartnerProfile.approved_at.is_(None))
            )
        ).scalar_one()
    )
    total_commissions = Decimal(
        str(
            (
                await session.execute(
                    select(func.coalesce(func.sum(PartnerCommission.commission_amount), 0))
                )
            ).scalar_one()
        )
    )
    total_conversions = int(
        (
            await session.execute(
                select(func.count()).select_from(ReferralTracking).where(ReferralTracking.status == "converted")
            )
        ).scalar_one()
    )
    return {
        "total_partners": total_partners,
        "pending_applications": pending_applications,
        "total_commissions": format(total_commissions, "f"),
        "total_conversions": total_conversions,
    }


__all__ = ["router"]
