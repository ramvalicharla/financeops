from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.rbac.evaluator import evaluate_permission
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import assign_user_role, create_role
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
            "correlation_id": "corr-rbac",
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
async def test_rbac_deny_over_allow_precedence(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    allow_role = await create_role(
        async_session,
        tenant_id=test_user.tenant_id,
        role_code="ALLOW_ROLE",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
    )
    deny_role = await create_role(
        async_session,
        tenant_id=test_user.tenant_id,
        role_code="DENY_ROLE",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
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
        role_id=allow_role.id,
        permission_id=permission.id,
        effect="allow",
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
    )
    await grant_role_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        role_id=deny_role.id,
        permission_id=permission.id,
        effect="deny",
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
    )
    now = datetime.now(UTC)
    await assign_user_role(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        role_id=allow_role.id,
        context_type="tenant",
        context_id=test_user.tenant_id,
        effective_from=now,
        effective_to=None,
        assigned_by=test_user.id,
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
    )
    await assign_user_role(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        role_id=deny_role.id,
        context_type="tenant",
        context_id=test_user.tenant_id,
        effective_from=now,
        effective_to=None,
        assigned_by=test_user.id,
        actor_user_id=test_user.id,
        correlation_id="corr-rbac",
    )
    result = await evaluate_permission(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        resource_type="revenue_run",
        action="execute",
        context_scope={"tenant": test_user.tenant_id},
        execution_timestamp=now,
    )
    assert result.allowed is False
    assert result.reason == "deny_over_allow"
