from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal
from financeops.modules.white_label.models import WhiteLabelAuditLog, WhiteLabelConfig
from financeops.modules.white_label.service import (
    enable_white_label,
    get_branding_for_domain,
    get_or_create_config,
    initiate_domain_verification,
    update_branding,
    verify_domain,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/white-label", tags=["white-label"])


class UpdateWhiteLabelConfigRequest(BaseModel):
    custom_domain: str | None = None
    brand_name: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_colour: str | None = None
    secondary_colour: str | None = None
    font_family: str | None = None
    hide_powered_by: bool | None = None
    custom_css: str | None = None
    support_email: str | None = None
    support_url: str | None = None


class DomainInitiateRequest(BaseModel):
    custom_domain: str


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _serialize_config(row: WhiteLabelConfig) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "is_enabled": row.is_enabled,
        "custom_domain": row.custom_domain,
        "domain_verified": row.domain_verified,
        "domain_verification_token": row.domain_verification_token,
        "brand_name": row.brand_name,
        "logo_url": row.logo_url,
        "favicon_url": row.favicon_url,
        "primary_colour": row.primary_colour,
        "secondary_colour": row.secondary_colour,
        "font_family": row.font_family,
        "hide_powered_by": row.hide_powered_by,
        "custom_css": row.custom_css,
        "support_email": row.support_email,
        "support_url": row.support_url,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_audit(row: WhiteLabelAuditLog) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "changed_by": str(row.changed_by),
        "field_changed": row.field_changed,
        "old_value": row.old_value,
        "new_value": row.new_value,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/config")
async def get_config_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await get_or_create_config(session, user.tenant_id)
    return _serialize_config(row)


@router.patch("/config")
async def patch_config_endpoint(
    body: UpdateWhiteLabelConfigRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    try:
        row = await update_branding(
            session,
            tenant_id=user.tenant_id,
            updated_by=user.id,
            updates=updates,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _serialize_config(row)


@router.post("/domain/verify-initiate")
async def domain_verify_initiate_endpoint(
    body: DomainInitiateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        return await initiate_domain_verification(
            session,
            tenant_id=user.tenant_id,
            custom_domain=body.custom_domain,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.post("/domain/verify-check")
async def domain_verify_check_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    verified = await verify_domain(session, tenant_id=user.tenant_id)
    row = await get_or_create_config(session, user.tenant_id)
    return {"verified": verified, "domain": row.custom_domain}


@router.get("/audit-log", response_model=Paginated[dict])
async def audit_log_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    stmt = select(WhiteLabelAuditLog).where(WhiteLabelAuditLog.tenant_id == user.tenant_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(WhiteLabelAuditLog.created_at.desc(), WhiteLabelAuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_audit(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/all", response_model=Paginated[dict])
async def admin_list_configs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    stmt = select(WhiteLabelConfig)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(WhiteLabelConfig.updated_at.desc(), WhiteLabelConfig.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_config(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/admin/{tenant_id}/enable")
async def admin_enable_tenant_endpoint(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = await enable_white_label(
        session,
        tenant_id=tenant_id,
        enabled_by=user.id,
    )
    return _serialize_config(row)


@router.get("/resolve/{domain}")
async def resolve_domain_endpoint(domain: str) -> dict:
    clean_domain = domain.strip().lower()
    async with AsyncSessionLocal() as session:
        try:
            row = await get_branding_for_domain(session, clean_domain)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.message) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="branding not found")
        return _serialize_config(row)


__all__ = ["router"]
