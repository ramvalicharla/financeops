from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.db.models.roles import CpRole
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash, get_previous_hash


async def _seed_iam_tenant(
    session: AsyncSession,
    *,
    display_name: str,
    slug: str,
) -> IamTenant:
    tenant_id = uuid.uuid4()
    payload = {
        "display_name": display_name,
        "slug": slug,
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
        "status": TenantStatus.active.value,
    }
    previous_hash = await get_previous_hash(session, IamTenant, tenant_id)
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=display_name,
        slug=slug,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(payload, previous_hash),
        previous_hash=previous_hash,
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _seed_cp_tenant(
    session: AsyncSession,
    *,
    tenant: IamTenant,
    tenant_code: str,
    billing_tier: str,
) -> None:
    payload = {
        "tenant_code": tenant_code,
        "display_name": tenant.display_name,
        "country_code": tenant.country,
        "region": "global",
        "billing_tier": billing_tier,
    }
    previous_hash = await get_previous_hash(session, CpTenant, tenant.id)
    session.add(
        CpTenant(
            id=tenant.id,
            tenant_id=tenant.id,
            tenant_code=tenant_code,
            display_name=tenant.display_name,
            country_code=tenant.country,
            region="global",
            billing_tier=billing_tier,
            status="active",
            correlation_id=None,
            chain_hash=compute_chain_hash(payload, previous_hash),
            previous_hash=previous_hash,
        )
    )
    await session.flush()


async def _seed_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_code: str,
) -> CpRole:
    payload = {
        "role_code": role_code,
        "role_scope": "tenant",
        "is_active": True,
        "description": f"{role_code} role",
    }
    previous_hash = await get_previous_hash(session, CpRole, tenant_id)
    role = CpRole(
        tenant_id=tenant_id,
        role_code=role_code,
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        description=f"{role_code} role",
        chain_hash=compute_chain_hash(payload, previous_hash),
        previous_hash=previous_hash,
    )
    session.add(role)
    await session.flush()
    return role


async def _seed_role_assignment(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> None:
    now = datetime.now(UTC)
    payload = {
        "user_id": str(user_id),
        "role_id": str(role_id),
        "context_type": "tenant",
        "context_id": str(tenant_id),
        "is_active": True,
        "effective_from": now.isoformat(),
    }
    previous_hash = await get_previous_hash(session, CpUserRoleAssignment, tenant_id)
    session.add(
        CpUserRoleAssignment(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role_id,
            context_type="tenant",
            context_id=tenant_id,
            is_active=True,
            effective_from=now,
            effective_to=None,
            assigned_by=user_id,
            correlation_id=None,
            chain_hash=compute_chain_hash(payload, previous_hash),
            previous_hash=previous_hash,
        )
    )
    await session.flush()


async def _seed_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Other User",
        role=UserRole.read_only,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_list_user_tenants_returns_only_accessible_tenants(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user: IamUser,
):
    accessible_tenant = await _seed_iam_tenant(
        async_session,
        display_name="Expansion Tenant",
        slug="expansion-tenant",
    )
    await _seed_cp_tenant(
        async_session,
        tenant=accessible_tenant,
        tenant_code="expansion",
        billing_tier="enterprise",
    )
    accessible_role = await _seed_role(
        async_session,
        tenant_id=accessible_tenant.id,
        role_code="tenant_member",
    )
    await _seed_role_assignment(
        async_session,
        tenant_id=accessible_tenant.id,
        user_id=test_user.id,
        role_id=accessible_role.id,
    )

    leaked_tenant = await _seed_iam_tenant(
        async_session,
        display_name="Leaked Tenant",
        slug="leaked-tenant",
    )
    await _seed_cp_tenant(
        async_session,
        tenant=leaked_tenant,
        tenant_code="leaked",
        billing_tier="starter",
    )
    other_user = await _seed_user(
        async_session,
        tenant_id=test_user.tenant_id,
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
    )
    leaked_role = await _seed_role(
        async_session,
        tenant_id=leaked_tenant.id,
        role_code="tenant_viewer",
    )
    await _seed_role_assignment(
        async_session,
        tenant_id=leaked_tenant.id,
        user_id=other_user.id,
        role_id=leaked_role.id,
    )

    await async_session.commit()

    response = await async_client.get(
        "/api/v1/user/tenants",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2

    by_id = {row["id"]: row for row in payload}
    assert str(accessible_tenant.id) in by_id
    assert str(leaked_tenant.id) not in by_id

    assert by_id[str(accessible_tenant.id)] == {
        "id": str(accessible_tenant.id),
        "slug": "expansion-tenant",
        "name": "Expansion Tenant",
        "role": "tenant_member",
        "status": "active",
        "plan": "enterprise",
    }
