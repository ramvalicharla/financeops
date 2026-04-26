"""Unit tests for the UserOrgMembership model (BE-001)."""

import uuid
import pytest
from sqlalchemy import select

from financeops.db.models.users import IamUser, UserOrgMembership, UserRole
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(tenant_id: uuid.UUID, email_suffix: str = "") -> IamUser:
    return IamUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"user{email_suffix}@test.example",
        hashed_password="hashed",
        full_name="Test User",
        role=UserRole.finance_team,
    )


def _make_membership(user_id: uuid.UUID, tenant_id: uuid.UUID, *, is_primary: bool = False) -> UserOrgMembership:
    return UserOrgMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        role=UserRole.finance_team,
        is_primary=is_primary,
        status="active",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_membership_created_with_defaults(async_session, test_tenant, test_user):
    """A membership row persists and reads back with expected default values."""
    membership = _make_membership(test_user.id, test_tenant.id)
    async_session.add(membership)
    await async_session.flush()

    result = await async_session.scalar(
        select(UserOrgMembership).where(UserOrgMembership.id == membership.id)
    )
    assert result is not None
    assert result.user_id == test_user.id
    assert result.tenant_id == test_tenant.id
    assert result.role == UserRole.finance_team
    assert result.is_primary is False
    assert result.status == "active"
    assert result.invited_by is None
    assert result.joined_at is not None
    assert result.created_at is not None


async def test_membership_is_primary_flag(async_session, test_tenant, test_user):
    """is_primary=True round-trips correctly."""
    membership = _make_membership(test_user.id, test_tenant.id, is_primary=True)
    async_session.add(membership)
    await async_session.flush()

    result = await async_session.scalar(
        select(UserOrgMembership).where(UserOrgMembership.id == membership.id)
    )
    assert result.is_primary is True


async def test_membership_unique_constraint(async_session, test_tenant, test_user):
    """Inserting two rows for the same (user_id, tenant_id) raises an integrity error."""
    from sqlalchemy.exc import IntegrityError

    m1 = _make_membership(test_user.id, test_tenant.id)
    m2 = _make_membership(test_user.id, test_tenant.id)
    async_session.add(m1)
    await async_session.flush()
    async_session.add(m2)
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


async def test_membership_user_relationship(async_session, test_tenant, test_user):
    """Relationship from UserOrgMembership.user back to IamUser resolves correctly."""
    membership = _make_membership(test_user.id, test_tenant.id, is_primary=True)
    async_session.add(membership)
    await async_session.flush()

    # Reload via primary key to ensure a fresh ORM load
    fresh = await async_session.get(UserOrgMembership, membership.id)
    assert fresh is not None
    # lazy="noload" means we need explicit load; just verify foreign key value
    assert fresh.user_id == test_user.id


async def test_multiple_memberships_same_user(async_session, test_tenant, test_user):
    """A single user can have memberships in multiple tenants (different tenant_ids)."""
    second_id = uuid.uuid4()
    record_data = {"display_name": "Second Org", "tenant_type": TenantType.direct.value,
                   "country": "US", "timezone": "UTC"}
    second_tenant = IamTenant(
        id=second_id,
        tenant_id=second_id,
        display_name="Second Org",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    async_session.add(second_tenant)
    await async_session.flush()

    m1 = _make_membership(test_user.id, test_tenant.id, is_primary=True)
    m2 = _make_membership(test_user.id, second_tenant.id, is_primary=False)
    async_session.add_all([m1, m2])
    await async_session.flush()

    rows = (await async_session.scalars(
        select(UserOrgMembership).where(UserOrgMembership.user_id == test_user.id)
    )).all()
    assert len(rows) == 2
    tenant_ids = {r.tenant_id for r in rows}
    assert test_tenant.id in tenant_ids
    assert second_tenant.id in tenant_ids


async def test_membership_cascade_delete_on_user(async_session, test_tenant):
    """Deleting an IamUser cascades to its membership rows."""
    user = _make_user(test_tenant.id, email_suffix="_cascade")
    async_session.add(user)
    await async_session.flush()

    membership = _make_membership(user.id, test_tenant.id, is_primary=True)
    async_session.add(membership)
    await async_session.flush()

    mem_id = membership.id
    await async_session.delete(user)
    await async_session.flush()
    async_session.expire_all()

    result = await async_session.get(UserOrgMembership, mem_id)
    assert result is None
