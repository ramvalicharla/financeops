from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.audit_writer import AuditWriter
from financeops.services.tenant_service import create_tenant, update_tenant_settings
from financeops.db.models.tenants import TenantType


@pytest.mark.asyncio
async def test_update_tenant_settings_uses_audit_writer(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.tenant_service.AuditWriter.flush_with_audit",
        wraps=AuditWriter.flush_with_audit,
    ) as flush_spy:
        updated = await update_tenant_settings(
            async_session,
            tenant=test_tenant,
            actor_user_id=test_tenant.id,
            display_name="Renamed Tenant",
            timezone_str="Asia/Kolkata",
        )
    assert updated.display_name == "Renamed Tenant"
    assert updated.timezone == "Asia/Kolkata"
    assert flush_spy.await_count == 1


@pytest.mark.asyncio
async def test_update_tenant_settings_no_changes_no_audit(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.tenant_service.AuditWriter.flush_with_audit",
        wraps=AuditWriter.flush_with_audit,
    ) as flush_spy:
        updated = await update_tenant_settings(
            async_session,
            tenant=test_tenant,
            actor_user_id=test_tenant.id,
            display_name=test_tenant.display_name,
            timezone_str=test_tenant.timezone,
        )
    assert updated.display_name == test_tenant.display_name
    assert updated.timezone == test_tenant.timezone
    assert flush_spy.await_count == 0


@pytest.mark.asyncio
async def test_create_tenant_defaults_to_asia_kolkata(async_session: AsyncSession):
    tenant = await create_tenant(
        async_session,
        display_name="India Default Tenant",
        tenant_type=TenantType.direct,
        country="IN",
    )
    assert tenant.timezone == "Asia/Kolkata"
