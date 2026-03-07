from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.enforcement.control_plane_authorizer import (
    CommandContext,
    ControlPlaneAuthorizer,
)
from financeops.platform.services.isolation.routing_service import create_isolation_route
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import assign_user_role, create_role
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.platform.db.models.modules import CpModuleRegistry


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
            "correlation_id": "corr-auth",
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


async def _seed_module_enablement(
    async_session: AsyncSession,
    *,
    tenant_id,
    actor_user_id,
    module_code: str,
    enabled: bool,
    correlation_id: str = "corr-auth",
) -> CpModuleRegistry:
    module = CpModuleRegistry(
        module_code=module_code,
        module_name=f"{module_code} module",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    await AuditWriter.insert_record(
        async_session,
        record=module,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.test.module.seed",
            resource_type="cp_module_registry",
            resource_id=str(module.id),
        ),
    )
    await set_module_enablement(
        async_session,
        tenant_id=tenant_id,
        module_id=module.id,
        enabled=enabled,
        enablement_source="test",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        effective_from=datetime.now(UTC),
        effective_to=None,
    )
    return module


@pytest.mark.asyncio
async def test_authorizer_blocks_when_module_disabled(async_session: AsyncSession, test_user) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    await assign_quota_to_tenant(
        async_session,
        tenant_id=test_user.tenant_id,
        quota_type="api_requests",
        window_type="tumbling",
        window_seconds=60,
        max_value=100,
        enforcement_mode="reject",
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    await create_isolation_route(
        async_session,
        tenant_id=test_user.tenant_id,
        isolation_tier="tier1",
        db_cluster="shared-primary",
        schema_name="public",
        worker_pool="shared-workers",
        region="us-east-1",
        migration_state="active",
        route_version=1,
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    module = await _seed_module_enablement(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        module_code="revenue",
        enabled=False,
        correlation_id="corr-auth",
    )
    decision = await ControlPlaneAuthorizer.authorize(
        async_session,
        CommandContext(
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            module_code=module.module_code,
            resource_type="revenue_run",
            resource_id="r1",
            action="execute",
            execution_mode="api",
            request_fingerprint="rf-1",
            correlation_id="corr-auth",
            context_scope={},
        ),
    )
    assert decision["decision"] == "deny"
    assert decision["reason_code"] == "MODULE_DISABLED"


@pytest.mark.asyncio
async def test_authorizer_allows_with_full_controls(async_session: AsyncSession, test_user) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    module = await _seed_module_enablement(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        module_code="revenue",
        enabled=True,
        correlation_id="corr-auth",
    )
    await assign_quota_to_tenant(
        async_session,
        tenant_id=test_user.tenant_id,
        quota_type="api_requests",
        window_type="tumbling",
        window_seconds=60,
        max_value=100,
        enforcement_mode="reject",
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    await create_isolation_route(
        async_session,
        tenant_id=test_user.tenant_id,
        isolation_tier="tier1",
        db_cluster="shared-primary",
        schema_name="public",
        worker_pool="shared-workers",
        region="us-east-1",
        migration_state="active",
        route_version=1,
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    role = await create_role(
        async_session,
        tenant_id=test_user.tenant_id,
        role_code="REV_EXEC",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    permission = await create_permission(
        async_session,
        actor_tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        permission_code="revenue.execute",
        resource_type="revenue_run",
        action="execute",
        description=None,
    )
    await grant_role_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        role_id=role.id,
        permission_id=permission.id,
        effect="allow",
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    await assign_user_role(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        role_id=role.id,
        context_type="tenant",
        context_id=test_user.tenant_id,
        effective_from=datetime.now(UTC),
        effective_to=None,
        assigned_by=test_user.id,
        actor_user_id=test_user.id,
        correlation_id="corr-auth",
    )
    decision = await ControlPlaneAuthorizer.authorize(
        async_session,
        CommandContext(
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            module_code=module.module_code,
            resource_type="revenue_run",
            resource_id="r1",
            action="execute",
            execution_mode="api",
            request_fingerprint="rf-1",
            correlation_id="corr-auth",
            context_scope={},
        ),
    )
    assert decision["decision"] == "allow"
    assert decision["context_token"]
