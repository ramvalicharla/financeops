from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenant_quota_assignments import CpTenantQuotaAssignment
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.tenancy.package_enablement import create_package
from financeops.platform.services.tenancy.tenant_provisioning import onboard_tenant


@pytest.mark.asyncio
async def test_onboard_tenant_creates_tenant_and_default_quotas(
    async_session: AsyncSession,
    test_user,
) -> None:
    package = await create_package(
        async_session,
        package_code=f"PKG-{uuid.uuid4().hex[:8]}",
        package_name="Starter",
        version="1.0.0",
        actor_tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        description="Starter package",
    )
    result = await onboard_tenant(
        async_session,
        tenant_code=f"TEN-{uuid.uuid4().hex[:8]}",
        display_name="Onboarded Tenant",
        country_code="US",
        region="us-east-1",
        billing_tier="pro",
        package_id=package.id,
        initiated_by=test_user.id,
        correlation_id="corr-onboard",
    )
    tenant_id = uuid.UUID(result["tenant_id"])

    tenant_result = await async_session.execute(
        select(CpTenant).where(CpTenant.tenant_id == tenant_id)
    )
    tenant = tenant_result.scalar_one()
    assert tenant.display_name == "Onboarded Tenant"
    assert tenant.status == "active"

    quota_result = await async_session.execute(
        select(CpTenantQuotaAssignment).where(CpTenantQuotaAssignment.tenant_id == tenant_id)
    )
    quotas = quota_result.scalars().all()
    assert len(quotas) >= 6
