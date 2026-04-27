"""Integration tests for GET/PATCH /api/v1/users/me/preferences (SP-4B).

T1 — GET returns sidebar_collapsed=null for new user (no preference set).
T2 — PATCH true writes true; subsequent GET returns true.
T3 — PATCH false writes false.
T4 — PATCH null clears preference; subsequent GET returns null.
T5 — Unauthenticated request returns 401.
T6 — User A cannot modify User B's preferences (isolation via current_user).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

GET_URL = "/api/v1/users/me/preferences"
PATCH_URL = "/api/v1/users/me/preferences"


def _auth(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _make_tenant(session: AsyncSession, *, display_name: str = "Test Co") -> IamTenant:
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


async def _make_user(
    session: AsyncSession,
    *,
    tenant: IamTenant,
    role: UserRole = UserRole.finance_team,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant.id,
        email=f"pref-test-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Prefs Test User",
        role=role,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# T1 — GET returns sidebar_collapsed=null for new user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_null_for_new_user(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(async_session)
    user = await _make_user(async_session, tenant=tenant)
    await async_session.commit()

    response = await async_client.get(GET_URL, headers=_auth(user))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sidebar_collapsed"] is None


# ---------------------------------------------------------------------------
# T2 — PATCH true; GET returns true
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_true_and_get_returns_true(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(async_session)
    user = await _make_user(async_session, tenant=tenant)
    await async_session.commit()

    patch_response = await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": True},
        headers=_auth(user),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["sidebar_collapsed"] is True

    get_response = await async_client.get(GET_URL, headers=_auth(user))
    assert get_response.status_code == 200
    assert get_response.json()["data"]["sidebar_collapsed"] is True


# ---------------------------------------------------------------------------
# T3 — PATCH false writes false
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_false_writes_false(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(async_session)
    user = await _make_user(async_session, tenant=tenant)
    await async_session.commit()

    # First set to true
    await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": True},
        headers=_auth(user),
    )

    # Now set to false
    patch_response = await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": False},
        headers=_auth(user),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["sidebar_collapsed"] is False


# ---------------------------------------------------------------------------
# T4 — PATCH null clears preference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_null_clears_preference(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(async_session)
    user = await _make_user(async_session, tenant=tenant)
    await async_session.commit()

    # Set a value
    await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": True},
        headers=_auth(user),
    )

    # Clear it
    patch_response = await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": None},
        headers=_auth(user),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["sidebar_collapsed"] is None

    get_response = await async_client.get(GET_URL, headers=_auth(user))
    assert get_response.json()["data"]["sidebar_collapsed"] is None


# ---------------------------------------------------------------------------
# T5 — Unauthenticated returns 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    assert (await async_client.get(GET_URL)).status_code == 401
    assert (await async_client.patch(PATCH_URL, json={"sidebar_collapsed": True})).status_code == 401


# ---------------------------------------------------------------------------
# T6 — User A's token cannot affect User B's sidebar preference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_a_cannot_modify_user_b_preferences(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(async_session)
    user_a = await _make_user(async_session, tenant=tenant)
    user_b = await _make_user(async_session, tenant=tenant)
    await async_session.commit()

    # User B sets their preference
    await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": True},
        headers=_auth(user_b),
    )

    # User A sets their own preference to false
    await async_client.patch(
        PATCH_URL,
        json={"sidebar_collapsed": False},
        headers=_auth(user_a),
    )

    # User B's preference is unchanged
    get_response = await async_client.get(GET_URL, headers=_auth(user_b))
    assert get_response.json()["data"]["sidebar_collapsed"] is True
