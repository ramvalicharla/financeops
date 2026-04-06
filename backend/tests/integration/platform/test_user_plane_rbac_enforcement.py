from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import (
    assign_user_role_now,
    create_role,
)
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
            "correlation_id": "corr-user-rbac",
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


async def _seed_deny_permission(
    async_session: AsyncSession,
    *,
    tenant_id,
    user_id,
    resource_type: str,
    action: str,
) -> None:
    permission = await create_permission(
        async_session,
        actor_tenant_id=tenant_id,
        actor_user_id=user_id,
        permission_code=f"{resource_type}.{action}.{uuid.uuid4().hex[:8]}",
        resource_type=resource_type,
        action=action,
        description="test deny permission",
    )
    role = await create_role(
        async_session,
        tenant_id=tenant_id,
        role_code=f"deny-{resource_type}-{uuid.uuid4().hex[:6]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="corr-user-rbac",
    )
    await grant_role_permission(
        async_session,
        tenant_id=tenant_id,
        role_id=role.id,
        permission_id=permission.id,
        effect="deny",
        actor_user_id=user_id,
        correlation_id="corr-user-rbac",
    )
    await assign_user_role_now(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role.id,
        context_type="tenant",
        context_id=tenant_id,
        assigned_by=user_id,
        actor_user_id=user_id,
        correlation_id="corr-user-rbac",
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_rbac_deny_blocks_tenant_user_management(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_deny_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        resource_type="tenant_user",
        action="manage",
    )
    response = await async_client.post(
        "/api/v1/tenants/me/users",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "email": "blocked-user@example.com",
            "full_name": "Blocked User",
            "role": "read_only",
            "entity_ids": [],
        },
    )
    assert response.status_code == 403
    assert "tenant_user.manage denied" in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_rbac_deny_blocks_workflow_mutation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_deny_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        resource_type="workflow",
        action="manage",
    )
    response = await async_client.post(
        "/api/v1/platform/workflows/templates",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "template_code": f"wf-{uuid.uuid4().hex[:8]}",
            "module_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 403
    assert "workflow.manage denied" in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_rbac_deny_blocks_hierarchy_mutation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_deny_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        resource_type="hierarchy",
        action="manage",
    )
    response = await async_client.post(
        "/api/v1/platform/org/organisations",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_code": f"ORG-{uuid.uuid4().hex[:6]}",
            "organisation_name": "Blocked Org",
            "parent_organisation_id": None,
        },
    )
    assert response.status_code == 403
    assert "hierarchy.manage denied" in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dynamic_rbac_deny_blocks_module_enablement_mutation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_cp_tenant(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )
    await _seed_deny_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        resource_type="module_enablement",
        action="manage",
    )
    module = CpModuleRegistry(
        module_code=f"mod-{uuid.uuid4().hex[:8]}",
        module_name="Module",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    async_session.add(module)
    await async_session.flush()

    response = await async_client.post(
        f"/api/v1/platform/modules/tenants/{test_user.tenant_id}/enablement",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_id": str(module.id),
            "enabled": True,
            "enablement_source": "test",
        },
    )
    assert response.status_code == 403
    assert "module_enablement.manage denied" in response.text
