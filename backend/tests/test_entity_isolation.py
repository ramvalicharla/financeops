from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_entity(async_client, user: IamUser, *, code: str, name: str) -> str:
    org_resp = await async_client.post(
        "/api/v1/platform/org/organisations",
        headers=_auth_headers(user),
        json={
            "organisation_code": f"ORG-{code}",
            "organisation_name": f"Org {name}",
            "parent_organisation_id": None,
        },
    )
    assert org_resp.status_code == 200
    organisation_id = org_resp.json()["data"]["id"]
    entity_resp = await async_client.post(
        "/api/v1/platform/org/entities",
        headers=_auth_headers(user),
        json={
            "entity_code": code,
            "entity_name": name,
            "organisation_id": organisation_id,
            "group_id": None,
            "base_currency": "INR",
            "country_code": "IN",
        },
    )
    assert entity_resp.status_code == 200
    return str(entity_resp.json()["data"]["id"])


@pytest.mark.asyncio
async def test_entity_isolation_finance_leader_sees_all(async_client, test_user: IamUser) -> None:
    await _create_entity(async_client, test_user, code="E001", name="Entity A")
    await _create_entity(async_client, test_user, code="E002", name="Entity B")

    response = await async_client.get("/api/v1/platform/entities", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload) >= 2


@pytest.mark.asyncio
async def test_entity_isolation_finance_team_sees_assigned_only(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E101", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E102", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    assign_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )
    assert assign_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/platform/entities", headers=_auth_headers(team_user))
    assert list_resp.status_code == 200
    entity_ids = {row["id"] for row in list_resp.json()["data"]}
    assert entity_a in entity_ids
    assert entity_b not in entity_ids


@pytest.mark.asyncio
async def test_entity_isolation_detail_access_denied(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E201", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E202", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    denied = await async_client.get(f"/api/v1/platform/entities/{entity_b}", headers=_auth_headers(team_user))
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_entity_isolation_detail_access_granted(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E301", name="Entity A")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    granted = await async_client.get(f"/api/v1/platform/entities/{entity_a}", headers=_auth_headers(team_user))
    assert granted.status_code == 200
    assert granted.json()["data"]["id"] == entity_a


@pytest.mark.asyncio
async def test_entity_isolation_finance_module_respects_assignment(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E401", name="Entity A")
    entity_b = await _create_entity(async_client, test_user, code="E402", name="Entity B")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_a,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    denied = await async_client.post(
        "/api/v1/tax/provision/compute",
        headers=_auth_headers(team_user),
        json={
            "period": "2026-03",
            "entity_id": entity_b,
            "applicable_tax_rate": "0.2517",
        },
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_entity_isolation_rls_not_bypassed(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_client, test_user, code="E501", name="Entity A")

    other_tenant_id = uuid.uuid4()
    other_tenant = IamTenant(
        id=other_tenant_id,
        tenant_id=other_tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="IN",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Other Tenant",
                "tenant_type": TenantType.direct.value,
                "country": "IN",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(other_tenant)

    other_user = IamUser(
        tenant_id=other_tenant_id,
        email=f"other-leader-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Other Leader",
        role=UserRole.finance_leader,
        is_active=True,
    )
    async_session.add(other_user)
    await async_session.flush()

    denied = await async_client.get(f"/api/v1/platform/entities/{entity_a}", headers=_auth_headers(other_user))
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_assert_entity_access_helper(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _create_entity(async_client, test_user, code="E601", name="Entity A")

    team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"fin-team-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(team_user)
    await async_session.flush()

    with pytest.raises(HTTPException):
        await assert_entity_access(
            session=async_session,
            tenant_id=test_user.tenant_id,
            entity_id=uuid.UUID(entity_id),
            user_id=team_user.id,
            user_role=team_user.role,
        )

    await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(team_user.id),
            "entity_id": entity_id,
            "effective_from": datetime.now(UTC).isoformat(),
            "effective_to": None,
        },
    )

    await assert_entity_access(
        session=async_session,
        tenant_id=test_user.tenant_id,
        entity_id=uuid.UUID(entity_id),
        user_id=team_user.id,
        user_role=team_user.role,
    )
