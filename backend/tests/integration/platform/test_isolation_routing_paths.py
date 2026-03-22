from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.isolation.routing_service import create_isolation_route, resolve_isolation_route
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
            "correlation_id": "corr-int-iso",
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
async def test_isolation_routing_endpoint_and_fail_closed(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    create_resp = await async_client.post(
        f"/api/v1/platform/isolation/tenants/{test_user.tenant_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "isolation_tier": "tier1",
            "db_cluster": "shared-primary",
            "schema_name": "public",
            "worker_pool": "shared-workers",
            "region": "us-east-1",
            "migration_state": "active",
            "route_version": 1,
            "effective_from": datetime.now(UTC).isoformat(),
        },
    )
    assert create_resp.status_code == 200

    resolve_resp = await async_client.get(
        f"/api/v1/platform/isolation/tenants/{test_user.tenant_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["data"]["db_cluster"] == "shared-primary"

    now = datetime.now(UTC)
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
        correlation_id="corr-int-iso",
    )
    with pytest.raises(ValidationError):
        await resolve_isolation_route(
            async_session,
            tenant_id=test_user.tenant_id,
            as_of=now + timedelta(minutes=2),
        )
