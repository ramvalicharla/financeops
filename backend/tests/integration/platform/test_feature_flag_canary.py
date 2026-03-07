from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
            "correlation_id": "corr-int-flag",
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
async def test_feature_flag_canary_rollout(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _seed_cp_tenant(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    module_response = await async_client.post(
        "/api/v1/platform/modules",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_code": f"fx-{uuid.uuid4().hex[:8]}",
            "module_name": "FX",
            "engine_context": "finance",
            "is_financial_impacting": True,
        },
    )
    assert module_response.status_code == 200
    module_id = module_response.json()["id"]

    create_flag = await async_client.post(
        f"/api/v1/platform/flags/tenants/{test_user.tenant_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_id": module_id,
            "flag_key": "canary.rollout",
            "flag_value": {},
            "rollout_mode": "canary",
            "compute_enabled": True,
            "write_enabled": False,
            "visibility_enabled": True,
            "target_scope_type": "canary",
            "target_scope_id": None,
            "traffic_percent": 0.0,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )
    assert create_flag.status_code == 200

    evaluate = await async_client.post(
        "/api/v1/platform/flags/evaluate",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "module_id": module_id,
            "flag_key": "canary.rollout",
            "request_fingerprint": "fingerprint-a",
        },
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["enabled"] is False
