"""
Tests for the hard MFA enforcement policy for platform_owner / platform_admin roles.

Policy under test (financeops/api/deps.py):
  IF user.role in {platform_owner, platform_admin}
  AND user.mfa_enabled is False
  AND request path is not in _MFA_SETUP_BYPASS_PATHS
  THEN raise HTTP 403 with "MFA is required for this role. Please complete MFA setup."

The check runs unconditionally regardless of the force_mfa_setup DB flag, so
manually clearing that flag cannot bypass MFA.
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

_MFA_REQUIRED_MESSAGE = "MFA is required for this role. Please complete MFA setup."

# A protected endpoint that a platform_owner/admin would normally reach.
_PROTECTED_URL = "/api/v1/platform/users"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_token(user: IamUser) -> str:
    return create_access_token(user.id, user.tenant_id, user.role.value)


def _extract_message(body: dict) -> str:
    """Extract the error message from either the envelope or a raw detail field."""
    # Wrapped: {"success": false, "error": {"message": "..."}, ...}
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message", ""))
    # Raw: {"detail": "..."}
    return str(body.get("detail", ""))


async def _make_platform_tenant(session: AsyncSession) -> IamTenant:
    tid = uuid.uuid4()
    record_data = {
        "display_name": "Platform Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tid,
        tenant_id=tid,
        display_name="Platform Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
        is_platform_tenant=True,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _make_regular_tenant(session: AsyncSession) -> IamTenant:
    tid = uuid.uuid4()
    record_data = {
        "display_name": "Regular Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tid,
        tenant_id=tid,
        display_name="Regular Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
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
    tenant: IamTenant,
    role: UserRole,
    mfa_enabled: bool,
    *,
    force_mfa_setup: bool = False,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant.id,
        email=f"mfatest-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="MFA Test User",
        role=role,
        is_active=True,
        mfa_enabled=mfa_enabled,
        force_mfa_setup=force_mfa_setup,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# platform_owner — MFA not enabled → 403 on any protected endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_owner_without_mfa_gets_403(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
        force_mfa_setup=False,  # flag cleared — hard policy must still fire
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "MFA is required" in _extract_message(response.json())


@pytest.mark.asyncio
async def test_platform_owner_without_mfa_403_exact_message(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert _MFA_REQUIRED_MESSAGE in _extract_message(response.json())


@pytest.mark.asyncio
async def test_platform_owner_with_mfa_enabled_passes_mfa_enforcement(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=True,
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    # Must not be rejected with the MFA enforcement error specifically
    msg = _extract_message(response.json())
    assert "MFA is required" not in msg


# ---------------------------------------------------------------------------
# platform_admin — same hard enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_admin_without_mfa_gets_403(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_admin,
        mfa_enabled=False,
        force_mfa_setup=False,  # flag cleared — hard policy must still fire
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "MFA is required" in _extract_message(response.json())


@pytest.mark.asyncio
async def test_platform_admin_with_mfa_enabled_passes_mfa_enforcement(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_admin,
        mfa_enabled=True,
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    msg = _extract_message(response.json())
    assert "MFA is required" not in msg


# ---------------------------------------------------------------------------
# Non-admin roles are NOT subject to the hard MFA policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finance_leader_without_mfa_is_not_blocked_by_hard_policy(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """finance_leader without MFA must not get the hard-policy 403."""
    tenant = await _make_regular_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.finance_leader,
        mfa_enabled=False,
        force_mfa_setup=False,
    )
    token = _make_token(user)

    # Use /api/v1/auth/me which a finance_leader can reach
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    msg = _extract_message(response.json())
    assert "MFA is required for this role" not in msg


# ---------------------------------------------------------------------------
# MFA setup bypass paths remain accessible before MFA is complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_owner_can_reach_mfa_setup_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The /api/v1/auth/mfa/setup endpoint must not be blocked by hard-enforce."""
    from financeops.api.v1.auth import generate_mfa_setup_token

    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
        force_mfa_setup=True,
    )
    setup_token = generate_mfa_setup_token(user)

    response = await async_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token}"},
    )
    # Must not be the MFA enforcement 403
    assert _extract_message(response.json()) != _MFA_REQUIRED_MESSAGE


@pytest.mark.asyncio
async def test_mfa_enforcement_does_not_block_auth_me(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """/api/v1/auth/me is in the bypass list and must remain accessible."""
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )
    token = _make_token(user)

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    # /api/v1/auth/me is bypassed — should succeed (200) for a valid token
    assert response.status_code == 200
    assert "MFA is required" not in _extract_message(response.json())


# ---------------------------------------------------------------------------
# Flag-clearing bypass scenario — the key regression test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clearing_force_mfa_setup_flag_does_not_bypass_hard_policy(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """
    Core regression test.

    Before this change, a platform_owner could bypass MFA by having force_mfa_setup
    cleared in the DB (e.g. via a direct SQL update).  The hard policy must reject
    them regardless of that flag.
    """
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
        force_mfa_setup=False,  # simulates DB flag having been cleared
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "MFA is required" in _extract_message(response.json())


@pytest.mark.asyncio
async def test_enabling_mfa_lifts_the_403_block(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """
    After mfa_enabled is set True on the user record, the same JWT must be able
    to pass the MFA enforcement gate (the user record is re-read from DB on every
    request — the JWT does not carry mfa_enabled).
    """
    tenant = await _make_platform_tenant(async_session)
    user = await _make_user(
        async_session,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )
    token = _make_token(user)

    # Step 1 — blocked before MFA enabled
    r1 = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 403
    assert "MFA is required" in _extract_message(r1.json())

    # Step 2 — enable MFA directly on the user record
    user.mfa_enabled = True
    await async_session.flush()

    # Step 3 — same token, same endpoint, must NOT be the MFA enforcement 403
    r2 = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "MFA is required" not in _extract_message(r2.json())
