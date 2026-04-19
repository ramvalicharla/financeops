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
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.platform.db.models import CpEntity, CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

_MFA_REQUIRED_MESSAGE = "MFA is required for this role. Please complete MFA setup."
_PROTECTED_URL = "/api/v1/platform/users"


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


def _make_token(user: IamUser) -> str:
    return create_access_token(user.id, user.tenant_id, user.role.value)


def _extract_message(body: dict) -> str:
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message", ""))
    return str(body.get("detail", ""))


async def _create_tenant(
    auth_session_factory,
    *,
    display_name: str,
    is_platform_tenant: bool,
) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": display_name,
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=display_name,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
        is_platform_tenant=is_platform_tenant,
    )
    org_payload = {
        "tenant_id": str(tenant_id),
        "organisation_code": f"ORG_{tenant_id.hex[:8].upper()}",
        "organisation_name": f"{display_name} Org",
    }
    org = CpOrganisation(
        tenant_id=tenant_id,
        organisation_code=org_payload["organisation_code"],
        organisation_name=org_payload["organisation_name"],
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id=f"mfa-org-{tenant_id.hex[:12]}",
        chain_hash=compute_chain_hash(org_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )

    async with auth_session_factory() as session:
        session.add(tenant)
        session.add(org)
        await session.flush()
        entity_payload = {
            "tenant_id": str(tenant_id),
            "entity_code": f"ENT_{tenant_id.hex[:8].upper()}",
            "entity_name": f"{display_name} Entity",
            "organisation_id": str(org.id),
        }
        entity = CpEntity(
            tenant_id=tenant_id,
            organisation_id=org.id,
            group_id=None,
            entity_code=entity_payload["entity_code"],
            entity_name=entity_payload["entity_name"],
            base_currency="INR",
            country_code="IN",
            status="active",
            deactivated_at=None,
            correlation_id=f"mfa-entity-{tenant_id.hex[:12]}",
            chain_hash=compute_chain_hash(entity_payload, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(entity)
        await session.commit()

    return tenant


async def _make_platform_tenant(auth_session_factory) -> IamTenant:
    return await _create_tenant(
        auth_session_factory,
        display_name="Platform Tenant",
        is_platform_tenant=True,
    )


async def _make_regular_tenant(auth_session_factory) -> IamTenant:
    return await _create_tenant(
        auth_session_factory,
        display_name="Regular Tenant",
        is_platform_tenant=False,
    )


async def _make_user(
    auth_session_factory,
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
    async with auth_session_factory() as session:
        session.add(user)
        await session.commit()
    return user


async def _set_user_mfa_enabled(
    auth_session_factory,
    *,
    user_id: uuid.UUID,
    mfa_enabled: bool,
) -> None:
    async with auth_session_factory() as session:
        await session.execute(
            update(IamUser)
            .where(IamUser.id == user_id)
            .values(mfa_enabled=mfa_enabled)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_platform_owner_without_mfa_gets_403(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
        force_mfa_setup=False,
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
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
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
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=True,
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "MFA is required" not in _extract_message(response.json())


@pytest.mark.asyncio
async def test_platform_admin_without_mfa_gets_403(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_admin,
        mfa_enabled=False,
        force_mfa_setup=False,
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
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_admin,
        mfa_enabled=True,
    )
    token = _make_token(user)

    response = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "MFA is required" not in _extract_message(response.json())


@pytest.mark.asyncio
async def test_finance_leader_without_mfa_is_not_blocked_by_hard_policy(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    tenant = await _make_regular_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.finance_leader,
        mfa_enabled=False,
        force_mfa_setup=False,
    )
    token = _make_token(user)

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "MFA is required for this role" not in _extract_message(response.json())


@pytest.mark.asyncio
async def test_platform_owner_can_reach_mfa_setup_endpoint(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    from financeops.api.v1.auth import generate_mfa_setup_token

    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
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
    assert _extract_message(response.json()) != _MFA_REQUIRED_MESSAGE


@pytest.mark.asyncio
async def test_mfa_enforcement_does_not_block_auth_me(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )
    token = _make_token(user)

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "MFA is required" not in _extract_message(response.json())


@pytest.mark.asyncio
async def test_clearing_force_mfa_setup_flag_does_not_bypass_hard_policy(
    async_client: AsyncClient,
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
        force_mfa_setup=False,
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
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )
    token = _make_token(user)

    first = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 403
    assert "MFA is required" in _extract_message(first.json())

    await _set_user_mfa_enabled(
        auth_session_factory,
        user_id=user.id,
        mfa_enabled=True,
    )

    second = await async_client.get(
        _PROTECTED_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "MFA is required" not in _extract_message(second.json())


@pytest.mark.asyncio
async def test_mfa_user_state_persisted_for_followup_reads(
    auth_session_factory,
) -> None:
    tenant = await _make_platform_tenant(auth_session_factory)
    user = await _make_user(
        auth_session_factory,
        tenant,
        UserRole.platform_owner,
        mfa_enabled=False,
    )

    await _set_user_mfa_enabled(
        auth_session_factory,
        user_id=user.id,
        mfa_enabled=True,
    )

    async with auth_session_factory() as session:
        refreshed = (
            await session.execute(select(IamUser).where(IamUser.id == user.id))
        ).scalar_one()
    assert refreshed.mfa_enabled is True
