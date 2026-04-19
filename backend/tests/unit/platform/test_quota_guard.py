from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.quotas.quota_guard import QuotaGuard, QuotaGuardRequest
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
            "correlation_id": "corr-quota",
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
async def test_quota_guard_rejects_on_limit_and_supports_idempotency(
    async_session: AsyncSession,
    test_user,
) -> None:
    await _seed_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    await assign_quota_to_tenant(
        async_session,
        tenant_id=test_user.tenant_id,
        quota_type="api_requests",
        window_type="tumbling",
        window_seconds=3600,
        max_value=1,
        enforcement_mode="reject",
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-quota",
    )
    op_id = uuid.uuid4()
    first = await QuotaGuard.check_and_record(
        async_session,
        QuotaGuardRequest(
            tenant_id=test_user.tenant_id,
            quota_type="api_requests",
            usage_delta=1,
            operation_id=op_id,
            idempotency_key="idem-1",
            request_fingerprint="fp-1",
            source_layer="api_ingress",
            actor_user_id=test_user.id,
            correlation_id="corr-quota",
        ),
    )
    replay = await QuotaGuard.check_and_record(
        async_session,
        QuotaGuardRequest(
            tenant_id=test_user.tenant_id,
            quota_type="api_requests",
            usage_delta=1,
            operation_id=op_id,
            idempotency_key="idem-1",
            request_fingerprint="fp-1",
            source_layer="api_ingress",
            actor_user_id=test_user.id,
            correlation_id="corr-quota",
        ),
    )
    second = await QuotaGuard.check_and_record(
        async_session,
        QuotaGuardRequest(
            tenant_id=test_user.tenant_id,
            quota_type="api_requests",
            usage_delta=1,
            operation_id=uuid.uuid4(),
            idempotency_key="idem-2",
            request_fingerprint="fp-2",
            source_layer="api_ingress",
            actor_user_id=test_user.id,
            correlation_id="corr-quota",
        ),
    )

    assert first["allowed"] is True
    assert replay["allowed"] is True
    assert replay["code"] == "IDEMPOTENT_REPLAY"
    assert second["allowed"] is False
    assert second["code"] == "QUOTA_EXCEEDED"
