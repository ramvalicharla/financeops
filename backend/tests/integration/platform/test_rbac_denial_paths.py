from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def _seed_cp_tenant(async_session: AsyncSession, *, tenant_id, actor_user_id) -> None:
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CpTenant,
        tenant_id=tenant_id,
        record_data={"tenant_code": f"TEN-{str(tenant_id)[:8]}", "status": "active"},
        values={
            "id": tenant_id,
            "tenant_code": f"TEN-{str(tenant_id)[:8]}",
            "display_name": "Tenant",
            "country_code": "US",
            "region": "us-east-1",
            "billing_tier": "pro",
            "status": "active",
            "correlation_id": "corr-int-rbac",
            "deactivated_at": None,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.test.seed",
            resource_type="cp_tenant",
            resource_id=str(tenant_id),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rbac_denial_path_without_assignments(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    create_mod = await async_client.post(
        "/api/v1/platform/modules",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_code": f"lease-{uuid.uuid4().hex[:8]}",
            "module_name": "Lease",
            "engine_context": "finance",
            "is_financial_impacting": True,
        },
    )
    assert create_mod.status_code == 200
    module_id = create_mod.json()["id"]
    module_code = create_mod.json()["module_code"]
    enable = await async_client.post(
        f"/api/v1/platform/modules/tenants/{test_user.tenant_id}/enablement",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"module_id": module_id, "enabled": True, "enablement_source": "test"},
    )
    assert enable.status_code == 200

    authorize = await async_client.post(
        "/api/v1/platform/modules/authorize",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "tenant_id": str(test_user.tenant_id),
            "user_id": str(test_user.id),
            "module_code": module_code,
            "resource_type": "lease_run",
            "resource_id": "run-1",
            "action": "execute",
            "execution_mode": "api",
            "request_fingerprint": "rf-rbac-deny",
            "correlation_id": "corr-int-rbac",
            "context_scope": {},
        },
    )
    assert authorize.status_code == 200
    payload = authorize.json()
    assert payload["decision"] == "deny"
    assert payload["reason_code"] == "PERMISSION_DENIED"
