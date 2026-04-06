from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    require_platform_admin,
    require_platform_owner,
)
from financeops.db.models.tenants import IamTenant, TenantStatus
from financeops.db.models.users import IamUser
from financeops.platform.schemas.tenants import TenantOnboardingRequest, TenantOnboardingResponse
from financeops.platform.services.tenancy.package_enablement import create_package
from financeops.platform.services.tenancy.tenant_provisioning import get_tenant, onboard_tenant
from financeops.shared_kernel.pagination import Paginated

router = APIRouter()


class TenantStatusUpdateRequest(BaseModel):
    status: TenantStatus


def _serialize_tenant(row: IamTenant) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "display_name": row.display_name,
        "slug": row.slug,
        "tenant_type": row.tenant_type.value,
        "country": row.country,
        "timezone": row.timezone,
        "status": row.status.value,
        "org_setup_complete": row.org_setup_complete,
        "org_setup_step": row.org_setup_step,
        "is_platform_tenant": row.is_platform_tenant,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/onboard", response_model=TenantOnboardingResponse, status_code=status.HTTP_202_ACCEPTED)
async def onboard_tenant_endpoint(
    body: TenantOnboardingRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")

    package = await create_package(
        session,
        package_code=body.package_code,
        package_name=f"{body.package_code} Package",
        version="1.0.0",
        actor_tenant_id=user.tenant_id,
        actor_user_id=user.id,
        description="Tenant onboarding default package",
    )
    result = await onboard_tenant(
        session,
        tenant_code=body.tenant_code,
        display_name=body.display_name,
        country_code=body.country_code,
        region=body.region,
        billing_tier=body.billing_tier,
        package_id=package.id,
        initiated_by=user.id,
        correlation_id=correlation_id,
    )
    await session.commit()
    return {
        "tenant_id": result["tenant_id"],
        "onboarding_status": result["onboarding_status"],
        "workflow_id": f"tenant-onboarding-{result['tenant_id']}",
        "correlation_id": correlation_id,
    }


@router.get("", response_model=Paginated[dict])
async def list_tenants_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: TenantStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> Paginated[dict]:
    stmt = select(IamTenant)
    if status_filter is not None:
        stmt = stmt.where(IamTenant.status == status_filter)

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            stmt.order_by(IamTenant.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_tenant(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{tenant_id}")
async def get_tenant_endpoint(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict:
    tenant = await get_tenant(session, tenant_id=tenant_id)
    return _serialize_tenant(tenant)


@router.patch("/{tenant_id}/status")
async def update_tenant_status_endpoint(
    tenant_id: uuid.UUID,
    body: TenantStatusUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict:
    row = (
        await session.execute(select(IamTenant).where(IamTenant.id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    row.status = body.status
    await session.commit()
    return _serialize_tenant(row)
