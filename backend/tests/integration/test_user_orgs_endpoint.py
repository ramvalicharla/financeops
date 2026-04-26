"""Integration tests for GET /api/v1/users/me/orgs (BE-001 Checkpoint 2).

T1 — Single-org user (backfill scenario) returns one row with is_primary=True.
T2 — Multi-org user returns correctly ordered list (primary first, then chronological).
T6 — User with zero active memberships returns empty list, not 404.
Defensive — Unauthenticated request returns 401.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserOrgMembership, UserRole
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

URL = "/api/v1/users/me/orgs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _make_tenant(
    session: AsyncSession,
    *,
    display_name: str,
    slug: str | None = None,
) -> IamTenant:
    tid = uuid.uuid4()
    record_data = {
        "display_name": display_name,
        "tenant_type": TenantType.direct.value,
        "country": "IN",
        "timezone": "Asia/Kolkata",
    }
    tenant = IamTenant(
        id=tid,
        tenant_id=tid,
        display_name=display_name,
        slug=slug,
        tenant_type=TenantType.direct,
        country="IN",
        timezone="Asia/Kolkata",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _make_user(session: AsyncSession, *, tenant: IamTenant) -> IamUser:
    user = IamUser(
        tenant_id=tenant.id,
        email=f"test-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_membership(
    session: AsyncSession,
    *,
    user: IamUser,
    tenant: IamTenant,
    is_primary: bool = False,
    status: str = "active",
    joined_at: datetime | None = None,
) -> UserOrgMembership:
    m = UserOrgMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
        is_primary=is_primary,
        status=status,
    )
    if joined_at is not None:
        m.joined_at = joined_at
    session.add(m)
    await session.flush()
    return m


# ---------------------------------------------------------------------------
# T1 — Single-org user returns one row with is_primary=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t1_single_org_user_returns_one_row(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant = await _make_tenant(async_session, display_name="Alpha Corp", slug="alpha-corp")
    user = await _make_user(async_session, tenant=tenant)
    await _make_membership(async_session, user=user, tenant=tenant, is_primary=True)
    await async_session.commit()

    response = await async_client.get(URL, headers=_auth(user))
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["org_id"] == str(tenant.id)
    assert item["org_name"] == "Alpha Corp"
    assert item["is_primary"] is True
    assert item["org_status"] == "active"
    assert item["role"] == UserRole.finance_team.value


# ---------------------------------------------------------------------------
# T2 — Multi-org user returns all active memberships, primary first
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t2_multi_org_user_ordered_correctly(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    now = datetime.now(UTC)
    tenant_a = await _make_tenant(async_session, display_name="Primary Org", slug="primary-org")
    tenant_b = await _make_tenant(async_session, display_name="Second Org", slug="second-org")
    tenant_c = await _make_tenant(async_session, display_name="Third Org", slug="third-org")

    # User belongs to tenant_a as home org
    user = await _make_user(async_session, tenant=tenant_a)

    t0 = now - timedelta(days=30)
    t1 = now - timedelta(days=20)
    t2 = now - timedelta(days=10)

    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True, joined_at=t0)
    await _make_membership(async_session, user=user, tenant=tenant_b, is_primary=False, joined_at=t1)
    await _make_membership(async_session, user=user, tenant=tenant_c, is_primary=False, joined_at=t2)
    await async_session.commit()

    response = await async_client.get(URL, headers=_auth(user))
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Primary first
    assert data["items"][0]["org_id"] == str(tenant_a.id)
    assert data["items"][0]["is_primary"] is True
    # Then chronological (B joined before C)
    assert data["items"][1]["org_id"] == str(tenant_b.id)
    assert data["items"][1]["is_primary"] is False
    assert data["items"][2]["org_id"] == str(tenant_c.id)
    assert data["items"][2]["is_primary"] is False


# ---------------------------------------------------------------------------
# T6 — User with no active memberships returns empty list, not 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t6_no_active_memberships_returns_empty_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant = await _make_tenant(async_session, display_name="Suspended Org")
    user = await _make_user(async_session, tenant=tenant)
    await _make_membership(async_session, user=user, tenant=tenant, is_primary=True, status="suspended")
    await async_session.commit()

    response = await async_client.get(URL, headers=_auth(user))
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Defensive — Unauthenticated returns 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client: AsyncClient):
    response = await async_client.get(URL)
    assert response.status_code == 401
