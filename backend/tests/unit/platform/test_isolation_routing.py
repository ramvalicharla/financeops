from __future__ import annotations

from datetime import UTC, datetime
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.isolation.routing_service import (
    create_isolation_route,
    resolve_isolation_route,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def _seed_tenant(async_session: AsyncSession, *, tenant_id, actor_user_id) -> None:
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
            "correlation_id": "corr-iso",
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
async def test_isolation_route_resolution_and_fail_closed(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    now = datetime.now(UTC)
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
        effective_from=now,
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-iso",
    )
    resolved = await resolve_isolation_route(
        async_session,
        tenant_id=test_user.tenant_id,
    )
    assert resolved.db_cluster == "shared-primary"

    await create_isolation_route(
        async_session,
        tenant_id=test_user.tenant_id,
        isolation_tier="tier1",
        db_cluster="",
        schema_name="public",
        worker_pool="shared-workers",
        region="us-east-1",
        migration_state="active",
        route_version=2,
        effective_from=now + timedelta(minutes=1),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-iso",
    )
    with pytest.raises(ValidationError):
        await resolve_isolation_route(
            async_session,
            tenant_id=test_user.tenant_id,
            as_of=now + timedelta(minutes=2),
        )
