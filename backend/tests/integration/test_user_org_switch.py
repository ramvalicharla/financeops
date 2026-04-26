"""Integration tests for POST /api/v1/users/me/orgs/{tenant_id}/switch (BE-001 Checkpoint 3).

T3  — Switch to a tenant the user IS a member of returns valid JWT + target_org info.
T4  — Switch to a tenant the user is NOT a member of returns 403.
T5  — Switch to a non-existent tenant returns 404.
T7  — Switch token successfully accesses target-tenant-scoped endpoint (org-setup/entities).
T8  — Switch token carries scope='user_switch'; 'switched_by' and 'platform_switch' absent.
T12 — Membership revoked mid-session causes next request to 401.
T13 — Forged switch token for a non-member tenant is rejected.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt as jose_jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import get_settings
from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserOrgMembership, UserRole
from financeops.modules.org_setup.models import OrgEntity, OrgGroup
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

SWITCH_URL = "/api/v1/users/me/orgs/{tenant_id}/switch"
ENTITIES_URL = "/api/v1/org-setup/entities"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(user: IamUser) -> dict[str, str]:
    """Home-org bearer token for the given user."""
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _bearer(token: str) -> dict[str, str]:
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
        slug=slug or f"t-{tid.hex[:8]}",
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
        email=f"switch-test-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Switch Test User",
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
) -> UserOrgMembership:
    m = UserOrgMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
        is_primary=is_primary,
        status=status,
    )
    session.add(m)
    await session.flush()
    return m


async def _make_org_group(
    session: AsyncSession,
    *,
    tenant: IamTenant,
) -> OrgGroup:
    """Create one OrgGroup per tenant (unique constraint on tenant_id)."""
    group = OrgGroup(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        group_name=f"{tenant.display_name} Group",
        country_of_incorp="India",
        country_code="IN",
        functional_currency="INR",
        reporting_currency="INR",
    )
    session.add(group)
    await session.flush()
    return group


async def _make_org_entity(
    session: AsyncSession,
    *,
    tenant: IamTenant,
    group: OrgGroup,
    legal_name: str,
) -> OrgEntity:
    entity = OrgEntity(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        org_group_id=group.id,
        legal_name=legal_name,
        entity_type="BRANCH",
        country_code="IN",
        functional_currency="INR",
        reporting_currency="INR",
        fiscal_year_start=4,
        applicable_gaap="INDAS",
    )
    session.add(entity)
    await session.flush()
    return entity


def _decode_switch_token(token: str) -> dict:
    """Decode a switch token using the test JWT secret (no verification of expiry)."""
    settings = get_settings()
    return jose_jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": False},
    )


# ---------------------------------------------------------------------------
# T3 — Switch to member tenant returns valid JWT + target_org info
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t3_switch_to_member_tenant_returns_jwt(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T3")
    tenant_b = await _make_tenant(async_session, display_name="Target Corp T3")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    await _make_membership(async_session, user=user, tenant=tenant_b)
    await async_session.commit()

    response = await async_client.post(
        SWITCH_URL.format(tenant_id=str(tenant_b.id)),
        headers=_auth(user),
    )
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert "switch_token" in data
    assert data["target_org"]["id"] == str(tenant_b.id)
    assert data["target_org"]["name"] == "Target Corp T3"
    assert data["target_org"]["role"] == UserRole.finance_team.value

    payload = _decode_switch_token(data["switch_token"])
    assert payload["sub"] == str(user.id)
    assert payload["tenant_id"] == str(tenant_b.id)


# ---------------------------------------------------------------------------
# T4 — Switch to non-member tenant returns 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t4_switch_to_non_member_tenant_returns_403(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T4")
    tenant_c = await _make_tenant(async_session, display_name="Unrelated Corp T4")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    # No membership in tenant_c
    await async_session.commit()

    response = await async_client.post(
        SWITCH_URL.format(tenant_id=str(tenant_c.id)),
        headers=_auth(user),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# T5 — Switch to non-existent tenant returns 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t5_switch_to_nonexistent_tenant_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T5")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    await async_session.commit()

    fake_id = uuid.uuid4()
    response = await async_client.post(
        SWITCH_URL.format(tenant_id=str(fake_id)),
        headers=_auth(user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T7 — Switch token accesses TARGET tenant's entities (not home tenant's)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t7_switch_token_accesses_target_tenant_entities(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T7")
    tenant_b = await _make_tenant(async_session, display_name="Target Corp T7")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    await _make_membership(async_session, user=user, tenant=tenant_b)

    # Two entities in A, one in B (one OrgGroup per tenant — unique constraint)
    group_a = await _make_org_group(async_session, tenant=tenant_a)
    group_b = await _make_org_group(async_session, tenant=tenant_b)
    await _make_org_entity(async_session, tenant=tenant_a, group=group_a, legal_name="A Entity 1")
    await _make_org_entity(async_session, tenant=tenant_a, group=group_a, legal_name="A Entity 2")
    entity_b = await _make_org_entity(async_session, tenant=tenant_b, group=group_b, legal_name="B Entity 1")
    await async_session.commit()

    # Get switch token
    switch_resp = await async_client.post(
        SWITCH_URL.format(tenant_id=str(tenant_b.id)),
        headers=_auth(user),
    )
    assert switch_resp.status_code == 200, switch_resp.text
    switch_token = switch_resp.json()["data"]["switch_token"]

    # Use switch token to access entities endpoint
    entities_resp = await async_client.get(
        ENTITIES_URL,
        headers=_bearer(switch_token),
    )
    assert entities_resp.status_code == 200, entities_resp.text

    entity_ids = [e["id"] for e in entities_resp.json()["data"]]
    assert str(entity_b.id) in entity_ids, "B's entity must be visible via switch token"
    assert all(
        e_id == str(entity_b.id) for e_id in entity_ids
    ), "Only B's entities should be returned — not home org A's"


# ---------------------------------------------------------------------------
# T8 — Switch token has scope='user_switch'; 'switched_by' and 'platform_switch' absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t8_switch_token_carries_user_switch_scope_not_platform_switch(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T8")
    tenant_b = await _make_tenant(async_session, display_name="Target Corp T8")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    await _make_membership(async_session, user=user, tenant=tenant_b)
    await async_session.commit()

    response = await async_client.post(
        SWITCH_URL.format(tenant_id=str(tenant_b.id)),
        headers=_auth(user),
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["switch_token"]

    payload = _decode_switch_token(token)
    assert payload.get("scope") == "user_switch"
    assert "switched_by" not in payload
    assert "platform_switch" not in str(payload)


# ---------------------------------------------------------------------------
# T12 — Membership revoked mid-session causes next request to 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t12_membership_revocation_mid_session_causes_401(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T12")
    tenant_b = await _make_tenant(async_session, display_name="Target Corp T12")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    membership_b = await _make_membership(async_session, user=user, tenant=tenant_b)
    group_b_t12 = await _make_org_group(async_session, tenant=tenant_b)
    await _make_org_entity(async_session, tenant=tenant_b, group=group_b_t12, legal_name="B Entity T12")
    await async_session.commit()

    # Get switch token — session is valid
    switch_resp = await async_client.post(
        SWITCH_URL.format(tenant_id=str(tenant_b.id)),
        headers=_auth(user),
    )
    assert switch_resp.status_code == 200, switch_resp.text
    switch_token = switch_resp.json()["data"]["switch_token"]

    # Action 1: switch token works before revocation
    first_resp = await async_client.get(ENTITIES_URL, headers=_bearer(switch_token))
    assert first_resp.status_code == 200, f"Pre-revocation call failed: {first_resp.text}"

    # Action 2: revoke the membership
    membership_b.status = "suspended"
    await async_session.flush()
    await async_session.commit()

    # Action 3: same switch token now 401
    second_resp = await async_client.get(ENTITIES_URL, headers=_bearer(switch_token))
    assert second_resp.status_code == 401, (
        f"Expected 401 after membership revoked, got {second_resp.status_code}: {second_resp.text}"
    )


# ---------------------------------------------------------------------------
# T13 — Forged switch token for a non-member tenant is rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t13_forged_switch_token_for_non_member_tenant_rejected(
    async_client: AsyncClient,
    async_session: AsyncSession,
):
    tenant_a = await _make_tenant(async_session, display_name="Home Corp T13")
    tenant_c = await _make_tenant(async_session, display_name="Non-Member Corp T13")
    user = await _make_user(async_session, tenant=tenant_a)
    await _make_membership(async_session, user=user, tenant=tenant_a, is_primary=True)
    # User is NOT a member of tenant_c
    await async_session.commit()

    settings = get_settings()
    forged_token = jose_jwt.encode(
        {
            "sub": str(user.id),
            "tenant_id": str(tenant_c.id),
            "role": "finance_team",
            "type": "access",
            "scope": "user_switch",
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = await async_client.get(ENTITIES_URL, headers=_bearer(forged_token))
    assert response.status_code == 401, (
        f"Expected 401 for forged switch token, got {response.status_code}: {response.text}"
    )
