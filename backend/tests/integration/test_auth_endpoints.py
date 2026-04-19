from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.platform.db.models import CpEntity, CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _unique_registration_payload(*, full_name: str, tenant_name_prefix: str) -> dict[str, object]:
    token = uuid.uuid4().hex[:8]
    return {
        "email": f"register-{token}@example.com",
        "password": "SecurePass123!",
        "full_name": full_name,
        "tenant_name": f"{tenant_name_prefix} {token}",
        "tenant_type": "direct",
        "country": "US",
    }


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(test_database_url: str):
    test_engine = create_async_engine(test_database_url, echo=False, poolclass=NullPool)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def auth_session_factory(engine):
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def test_tenant(auth_session_factory) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Test Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Test Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    async with auth_session_factory() as session:
        session.add(tenant)
        await session.commit()
    return tenant


@pytest_asyncio.fixture
async def test_user(auth_session_factory, test_tenant: IamTenant) -> IamUser:
    user = IamUser(
        tenant_id=test_tenant.id,
        email="testuser@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    org_payload = {
        "tenant_id": str(test_tenant.id),
        "organisation_code": "ORG_DEFAULT",
        "organisation_name": "Default Org",
    }
    org = CpOrganisation(
        tenant_id=test_tenant.id,
        organisation_code="ORG_DEFAULT",
        organisation_name="Default Org",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id="test-default-org",
        chain_hash=compute_chain_hash(org_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    async with auth_session_factory() as session:
        await session.execute(
            delete(IamUser).where(func.lower(IamUser.email) == "testuser@example.com")
        )
        session.add(user)
        session.add(org)
        await session.flush()
        entity_payload = {
            "tenant_id": str(test_tenant.id),
            "entity_code": "ENT_DEFAULT",
            "entity_name": "Default Entity",
            "organisation_id": str(org.id),
        }
        entity = CpEntity(
            tenant_id=test_tenant.id,
            organisation_id=org.id,
            group_id=None,
            entity_code="ENT_DEFAULT",
            entity_name="Default Entity",
            base_currency="INR",
            country_code="IN",
            status="active",
            deactivated_at=None,
            correlation_id="test-default-entity",
            chain_hash=compute_chain_hash(entity_payload, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(entity)
        await session.commit()

    return user


@pytest_asyncio.fixture
async def async_client(engine) -> AsyncClient:
    from financeops.api.deps import get_async_session
    from financeops.main import app

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    original_startup_errors = getattr(app.state, "startup_errors", [])
    original_migration_state = getattr(app.state, "migration_state", None)
    app.state.startup_errors = []
    app.state.migration_state = {
        "status": "ok",
        "current_revision": "test",
        "head_revision": "test",
        "detail": None,
    }

    async def override_session(request: Request):
        tenant_id = str(getattr(request.state, "tenant_id", "") or "")
        if not tenant_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                from financeops.core.security import decode_token

                token = auth_header[7:]
                try:
                    payload = decode_token(token)
                except Exception:
                    payload = {}
                tenant_id = str(payload.get("tenant_id", "") or "")

        async with session_factory() as session:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            try:
                yield session
            finally:
                if tenant_id:
                    try:
                        await clear_tenant_context(session)
                    except Exception:
                        await session.rollback()

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
    app.state.startup_errors = original_startup_errors
    app.state.migration_state = original_migration_state


@pytest.mark.asyncio
async def test_register_creates_tenant_and_user(async_client: AsyncClient):
    payload = _unique_registration_payload(
        full_name="New User",
        tenant_name_prefix="New Corp",
    )
    payload["terms_accepted"] = True
    response = await async_client.post(
        "/api/v1/auth/register",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "user_id" in data
    assert "tenant_id" in data
    assert data["mfa_setup_required"] is True


@pytest.mark.asyncio
async def test_registration_stores_terms_accepted_at(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    payload = _unique_registration_payload(
        full_name="Terms User",
        tenant_name_prefix="Terms Corp",
    )
    payload["terms_accepted"] = True
    response = await async_client.post(
        "/api/v1/auth/register",
        json=payload,
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["data"]["user_id"])
    async with auth_session_factory() as session:
        user = (
            await session.execute(
                select(IamUser).where(IamUser.id == user_id)
            )
        ).scalar_one()
    assert user.terms_accepted_at is not None
    assert user.terms_version_accepted == "2026-03-01"


@pytest.mark.asyncio
async def test_registration_requires_terms_acceptance(async_client: AsyncClient) -> None:
    payload = _unique_registration_payload(
        full_name="No Terms User",
        tenant_name_prefix="No Terms Corp",
    )
    response = await async_client.post(
        "/api/v1/auth/register",
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_tokens(
    async_client: AsyncClient, test_user
):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_commits_session_when_tokens_issued(
    async_client: AsyncClient,
    test_user,
    monkeypatch,
) -> None:
    commit_spy = AsyncMock()
    monkeypatch.setattr("financeops.api.v1.auth.commit_session", commit_spy)

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )

    assert response.status_code == 200
    assert commit_spy.await_count == 1


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(
    async_client: AsyncClient, test_user
):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_malformed_hash_returns_401(
    async_client: AsyncClient,
    auth_session_factory,
    test_user,
) -> None:
    async with auth_session_factory() as session:
        malformed_user = IamUser(
            tenant_id=test_user.tenant_id,
            email=f"bad-hash-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-valid-bcrypt-hash",
            full_name="Bad Hash User",
            role=test_user.role,
            is_active=True,
            mfa_enabled=False,
        )
        session.add(malformed_user)
        await session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": malformed_user.email, "password": "AnyPassword123!"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_is_case_insensitive_for_existing_user_rows(
    async_client: AsyncClient,
    auth_session_factory,
    test_user,
) -> None:
    mixed_case_email = f"Invited.User.{uuid.uuid4().hex[:8]}@Example.COM"
    async with auth_session_factory() as session:
        invited_user = IamUser(
            tenant_id=test_user.tenant_id,
            email=mixed_case_email,
            hashed_password=hash_password("InvitePass123!"),
            full_name="Invited User",
            role=test_user.role,
            is_active=True,
            mfa_enabled=False,
        )
        session.add(invited_user)
        await session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": mixed_case_email.lower(), "password": "InvitePass123!"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_accessing_protected_endpoint_without_token_returns_401(
    async_client: AsyncClient,
):
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(
    async_client: AsyncClient, test_access_token: str, test_user
):
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == test_user.email
    assert "tenant" in data
    assert "coa_status" in data["tenant"]
    assert "onboarding_score" in data["tenant"]
    assert "entity_roles" in data


@pytest.mark.asyncio
async def test_get_entity_roles_with_valid_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/auth/entity-roles",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    assert {"entity_id", "entity_name", "role", "currency"} <= set(data[0].keys())


@pytest.mark.asyncio
async def test_refresh_token_rotation(
    async_client: AsyncClient, test_user
):
    # Login to get initial tokens
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    initial_refresh = login_resp.json()["data"]["refresh_token"]

    # Rotate
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()["data"]
    assert "access_token" in new_tokens
    new_refresh = new_tokens["refresh_token"]
    assert new_refresh != initial_refresh

    # Old token should now be invalid
    old_refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert old_refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_commits_rotated_session(
    async_client: AsyncClient,
    test_user,
    monkeypatch,
) -> None:
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    initial_refresh = login_resp.json()["data"]["refresh_token"]

    commit_spy = AsyncMock()
    monkeypatch.setattr("financeops.api.v1.auth.commit_session", commit_spy)

    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )

    assert refresh_resp.status_code == 200
    assert commit_spy.await_count == 1


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    refresh_token = login_resp.json()["data"]["refresh_token"]

    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # After logout, refresh should fail
    retry_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert retry_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_sets_tenant_context_from_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["data"]["refresh_token"]

    with patch(
        "financeops.api.v1.auth.set_tenant_context",
        new_callable=AsyncMock,
    ) as set_ctx:
        refresh_resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    assert refresh_resp.status_code == 200
    assert set_ctx.await_count == 1


@pytest.mark.asyncio
async def test_logout_sets_tenant_context_from_refresh_token(
    async_client: AsyncClient, test_user
):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "TestPass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["data"]["refresh_token"]

    with patch(
        "financeops.api.v1.auth.set_tenant_context",
        new_callable=AsyncMock,
    ) as set_ctx:
        logout_resp = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
    assert logout_resp.status_code == 200
    assert set_ctx.await_count == 1
