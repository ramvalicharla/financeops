from __future__ import annotations

from uuid import UUID

from temporalio import activity

from financeops.db.session import tenant_session
from financeops.platform.services.tenancy.tenant_provisioning import validate_tenant_active
from financeops.platform.temporal.tenant_onboarding_workflows import TenantOnboardingWorkflowInput


def _parse_uuid(raw: str) -> UUID:
    return UUID(str(raw))


@activity.defn(name="tenant_onboarding_validate_activity")
async def tenant_onboarding_validate_activity(payload: TenantOnboardingWorkflowInput) -> dict:
    tenant_id = _parse_uuid(payload.tenant_id)
    async with tenant_session(tenant_id) as session:
        await validate_tenant_active(session, tenant_id=tenant_id)
    return {"tenant_id": payload.tenant_id, "validated": True}


@activity.defn(name="tenant_onboarding_finalize_activity")
async def tenant_onboarding_finalize_activity(payload: TenantOnboardingWorkflowInput) -> dict:
    return {
        "tenant_id": payload.tenant_id,
        "correlation_id": payload.correlation_id,
        "requested_by": payload.requested_by,
        "config_hash": payload.config_hash,
    }
