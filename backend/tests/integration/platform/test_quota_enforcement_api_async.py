from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.quotas.quota_guard import QuotaGuard, QuotaGuardRequest
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
            "correlation_id": "corr-int-quota",
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
async def test_quota_enforced_at_api_and_internal_paths(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    assign = await async_client.post(
        f"/api/v1/platform/quotas/tenants/{test_user.tenant_id}/assignments",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "quota_type": "api_requests",
            "window_type": "tumbling",
            "window_seconds": 3600,
            "max_value": 1,
            "enforcement_mode": "reject",
            "effective_from": datetime.now(UTC).isoformat(),
        },
    )
    assert assign.status_code == 200

    first = await async_client.post(
        "/api/v1/platform/quotas/check",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "quota_type": "api_requests",
            "usage_delta": 1,
            "operation_id": str(uuid.uuid4()),
            "idempotency_key": "idem-api-1",
            "request_fingerprint": "fp-api-1",
            "source_layer": "api_ingress",
        },
    )
    second = await async_client.post(
        "/api/v1/platform/quotas/check",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "quota_type": "api_requests",
            "usage_delta": 1,
            "operation_id": str(uuid.uuid4()),
            "idempotency_key": "idem-api-2",
            "request_fingerprint": "fp-api-2",
            "source_layer": "api_ingress",
        },
    )
    assert first.status_code == 200
    assert first.json()["data"]["allowed"] is True
    assert second.status_code == 200
    assert second.json()["data"]["allowed"] is False

    internal = await QuotaGuard.check_and_record(
        async_session,
        QuotaGuardRequest(
            tenant_id=test_user.tenant_id,
            quota_type="api_requests",
            usage_delta=1,
            operation_id=uuid.uuid4(),
            idempotency_key="idem-internal-1",
            request_fingerprint="fp-internal-1",
            source_layer="internal_command",
            actor_user_id=test_user.id,
            correlation_id="corr-int-quota",
        ),
    )
    assert internal["allowed"] is False
