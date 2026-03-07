from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.db.models.users import IamUser
from financeops.platform.schemas.tenants import TenantOnboardingRequest, TenantOnboardingResponse
from financeops.platform.services.tenancy.package_enablement import create_package
from financeops.platform.services.tenancy.tenant_provisioning import get_tenant, onboard_tenant

router = APIRouter()


@router.post("/onboard", response_model=TenantOnboardingResponse, status_code=status.HTTP_202_ACCEPTED)
async def onboard_tenant_endpoint(
    body: TenantOnboardingRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
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


@router.get("/{tenant_id}")
async def get_tenant_endpoint(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    del user
    tenant = await get_tenant(session, tenant_id=tenant_id)
    return {
        "id": str(tenant.id),
        "tenant_id": str(tenant.tenant_id),
        "tenant_code": tenant.tenant_code,
        "display_name": tenant.display_name,
        "status": tenant.status,
    }
