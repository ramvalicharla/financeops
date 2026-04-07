from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.db.models.feature_flags import CpModuleFeatureFlag
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _create_platform_user(
    async_session: AsyncSession,
    *,
    tenant_id,
    role: UserRole,
    email: str,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=role.value,
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    async_session.add(user)
    await async_session.flush()
    return user


def _auth_header(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_platform_admin_cannot_change_tenant_lifecycle(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin = await _create_platform_user(
        async_session,
        tenant_id=test_tenant.id,
        role=UserRole.platform_admin,
        email="platform-admin-tenant@example.com",
    )
    response = await async_client.patch(
        f"/api/v1/platform/tenants/{test_tenant.id}/status",
        headers=_auth_header(admin),
        json={"status": "suspended"},
    )
    assert response.status_code == 403
    assert "platform_owner role required" in response.text


@pytest.mark.asyncio
async def test_platform_admin_cannot_mutate_billing_plans(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin = await _create_platform_user(
        async_session,
        tenant_id=test_tenant.id,
        role=UserRole.platform_admin,
        email="platform-admin-plan@example.com",
    )
    response = await async_client.post(
        "/api/v1/platform/plans",
        headers=_auth_header(admin),
        json={
            "name": "Starter",
            "plan_tier": "starter",
            "pricing_type": "flat",
            "price": "10.00",
            "billing_cycle": "monthly",
            "currency": "USD",
            "included_credits": 0,
            "max_entities": 1,
            "max_connectors": 1,
            "max_users": 1,
            "modules_enabled": {},
            "trial_days": 0,
            "annual_discount_pct": "0",
            "is_active": True,
            "entitlements": [],
        },
    )
    assert response.status_code == 403
    assert "platform_owner role required" in response.text


@pytest.mark.asyncio
async def test_platform_admin_cannot_mutate_rbac_catalog(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin = await _create_platform_user(
        async_session,
        tenant_id=test_tenant.id,
        role=UserRole.platform_admin,
        email="platform-admin-rbac@example.com",
    )
    response = await async_client.post(
        "/api/v1/platform/rbac/permissions",
        headers=_auth_header(admin),
        json={
            "permission_code": f"tenant_user.manage.{uuid.uuid4().hex[:6]}",
            "resource_type": "tenant_user",
            "action": "manage",
            "description": "test",
        },
    )
    assert response.status_code == 403
    assert "platform_owner role required" in response.text


@pytest.mark.asyncio
async def test_platform_admin_cannot_destructively_update_feature_flags(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin = await _create_platform_user(
        async_session,
        tenant_id=test_tenant.id,
        role=UserRole.platform_admin,
        email="platform-admin-flags@example.com",
    )
    module = CpModuleRegistry(
        module_code=f"flagmod-{uuid.uuid4().hex[:8]}",
        module_name="Flag Module",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    async_session.add(module)
    await async_session.flush()

    flag_record = {
        "module_id": str(module.id),
        "flag_key": "enabled",
        "rollout_mode": "on",
        "target_scope_type": "tenant",
        "effective_from": datetime.now(UTC).isoformat(),
    }
    flag = CpModuleFeatureFlag(
        tenant_id=test_tenant.id,
        module_id=module.id,
        flag_key="enabled",
        flag_value={"enabled": True},
        rollout_mode="on",
        compute_enabled=True,
        write_enabled=True,
        visibility_enabled=True,
        target_scope_type="tenant",
        target_scope_id=None,
        traffic_percent=None,
        effective_from=datetime.now(UTC),
        effective_to=None,
        correlation_id="test-flag",
        chain_hash=compute_chain_hash(flag_record, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(flag)
    await async_session.flush()

    response = await async_client.put(
        f"/api/v1/platform/flags/{flag.id}",
        headers=_auth_header(admin),
        json={"enabled": False},
    )
    assert response.status_code == 403
    assert "platform_owner role required" in response.text
