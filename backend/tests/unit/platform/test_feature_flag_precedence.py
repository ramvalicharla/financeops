from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.feature_flags.flag_service import (
    create_feature_flag,
    evaluate_feature_flag,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def _seed(async_session: AsyncSession, *, tenant_id, actor_user_id) -> CpModuleRegistry:
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
            "correlation_id": "corr-flag",
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
    module = CpModuleRegistry(
        module_code=f"mod-{str(tenant_id)[:8]}",
        module_name="Module",
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
    return module


@pytest.mark.asyncio
async def test_feature_flag_scope_precedence_entity_over_tenant(
    async_session: AsyncSession,
    test_user,
) -> None:
    module = await _seed(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    now = datetime.now(UTC)
    entity_id = uuid.uuid4()
    await create_feature_flag(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        flag_key="rev.enabled",
        flag_value={},
        rollout_mode="on",
        compute_enabled=True,
        write_enabled=True,
        visibility_enabled=True,
        target_scope_type="tenant",
        target_scope_id=None,
        traffic_percent=None,
        effective_from=now,
        effective_to=now + timedelta(days=10),
        actor_user_id=test_user.id,
        correlation_id="corr-flag",
    )
    await create_feature_flag(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        flag_key="rev.enabled",
        flag_value={},
        rollout_mode="off",
        compute_enabled=False,
        write_enabled=False,
        visibility_enabled=False,
        target_scope_type="entity",
        target_scope_id=entity_id,
        traffic_percent=None,
        effective_from=now + timedelta(minutes=1),
        effective_to=now + timedelta(days=10),
        actor_user_id=test_user.id,
        correlation_id="corr-flag",
    )

    result = await evaluate_feature_flag(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        flag_key="rev.enabled",
        request_fingerprint="fp-flag",
        user_id=test_user.id,
        entity_id=entity_id,
        as_of=now + timedelta(minutes=2),
    )
    assert result["enabled"] is False
    assert result["write_enabled"] is False
