from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient, Request as HttpxRequest
from itsdangerous import URLSafeSerializer
from sqlalchemy import select, update

from financeops.config import settings
from financeops.core.security import hash_password, verify_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamSession, IamUser, UserRole
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import finalize_session_success
from financeops.platform.db.models import CpEntity, CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


@pytest_asyncio.fixture
async def test_tenant(api_session_factory) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Security Test Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Security Test Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    async with api_session_factory() as session:
        session.add(tenant)
        await session.commit()
    return tenant


@pytest_asyncio.fixture
async def test_user(api_session_factory, test_tenant: IamTenant) -> IamUser:
    email = f"security-user-{uuid.uuid4().hex[:8]}@example.com"
    user = IamUser(
        tenant_id=test_tenant.id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Security User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    org_payload = {
        "tenant_id": str(test_tenant.id),
        "organisation_code": f"ORG_{uuid.uuid4().hex[:8].upper()}",
        "organisation_name": "Security Org",
    }
    org = CpOrganisation(
        tenant_id=test_tenant.id,
        organisation_code=org_payload["organisation_code"],
        organisation_name="Security Org",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id=f"test-security-org-{uuid.uuid4().hex[:8]}",
        chain_hash=compute_chain_hash(org_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    async with api_session_factory() as session:
        session.add(user)
        session.add(org)
        await session.flush()
        entity_payload = {
            "tenant_id": str(test_tenant.id),
            "entity_code": f"ENT_{uuid.uuid4().hex[:8].upper()}",
            "entity_name": "Security Entity",
            "organisation_id": str(org.id),
        }
        entity = CpEntity(
            tenant_id=test_tenant.id,
            organisation_id=org.id,
            group_id=None,
            entity_code=entity_payload["entity_code"],
            entity_name="Security Entity",
            base_currency="INR",
            country_code="IN",
            status="active",
            deactivated_at=None,
            correlation_id=f"test-security-entity-{uuid.uuid4().hex[:8]}",
            chain_hash=compute_chain_hash(entity_payload, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(entity)
        await session.commit()
    return user


@pytest_asyncio.fixture
async def async_client(api_session_factory) -> AsyncClient:
    from financeops.api.deps import get_async_session
    from financeops.main import app

    original_startup_errors = getattr(app.state, "startup_errors", [])
    original_migration_state = getattr(app.state, "migration_state", None)
    app.state.startup_errors = []
    app.state.migration_state = {
        "status": "ok",
        "current_revision": "test",
        "head_revision": "test",
        "detail": None,
    }

    csrf_serializer = URLSafeSerializer(settings.SECRET_KEY, "csrftoken")

    async def _inject_csrf_token(request: HttpxRequest) -> None:
        if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        if "x-csrftoken" in request.headers:
            return
        existing_cookie = request.headers.get("cookie", "")
        if "csrftoken=" in existing_cookie:
            for cookie_part in existing_cookie.split(";"):
                part = cookie_part.strip()
                if part.startswith("csrftoken="):
                    request.headers["x-csrftoken"] = part.split("=", 1)[1]
                    return
            return
        token = csrf_serializer.dumps("test-csrf")
        request.headers["x-csrftoken"] = token
        csrf_cookie = f"csrftoken={token}"
        request.headers["cookie"] = f"{existing_cookie}; {csrf_cookie}" if existing_cookie else csrf_cookie

    async def _consume_response(response) -> None:
        await response.aread()

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

        async with api_session_factory() as session:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            try:
                yield session
                await finalize_session_success(session)
            except Exception:
                await session.rollback()
                raise
            finally:
                if tenant_id and session.in_transaction():
                    try:
                        await clear_tenant_context(session)
                    except Exception:
                        await session.rollback()

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        event_hooks={
            "request": [_inject_csrf_token],
            "response": [_consume_response],
        },
    ) as client:
        yield client
    app.dependency_overrides.clear()
    app.state.startup_errors = original_startup_errors
    app.state.migration_state = original_migration_state


async def _set_force_password_change(
    api_session_factory,
    *,
    user_id: uuid.UUID,
    force_password_change: bool,
) -> None:
    async with api_session_factory() as session:
        await session.execute(
            update(IamUser)
            .where(IamUser.id == user_id)
            .values(force_password_change=force_password_change)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_password_change_revokes_old_refresh_token(
    async_client: AsyncClient,
    api_session_factory,
    test_user: IamUser,
) -> None:
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert login.status_code == 200
    old_refresh_token = login.json()["data"]["refresh_token"]

    await _set_force_password_change(
        api_session_factory,
        user_id=test_user.id,
        force_password_change=True,
    )

    password_change_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert password_change_login.status_code == 200
    change_token = password_change_login.json()["data"]["password_change_token"]

    change = await async_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "NewPass123!"},
        headers={"Authorization": f"Bearer {change_token}", "Idempotency-Key": "pwd-change-refresh"},
    )
    assert change.status_code == 200

    refresh = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_password_change_returns_new_token_pair(
    async_client: AsyncClient,
    api_session_factory,
    test_user: IamUser,
) -> None:
    await _set_force_password_change(
        api_session_factory,
        user_id=test_user.id,
        force_password_change=True,
    )

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert login.status_code == 200
    change_token = login.json()["data"]["password_change_token"]

    response = await async_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "NewPass123!"},
        headers={"Authorization": f"Bearer {change_token}", "Idempotency-Key": "pwd-change-token-pair"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "password_changed"
    assert isinstance(payload["access_token"], str)
    assert isinstance(payload["refresh_token"], str)
    assert payload["token_type"] == "bearer"

    async with api_session_factory() as session:
        refreshed_user = await session.get(IamUser, test_user.id)
        assert refreshed_user is not None
        assert verify_password("NewPass123!", refreshed_user.hashed_password) is True
        assert refreshed_user.force_password_change is False
        assert refreshed_user.password_changed_at is not None

        active_sessions = (
            await session.execute(
                select(IamSession).where(
                    IamSession.user_id == test_user.id,
                    IamSession.revoked_at.is_(None),
                )
            )
        ).scalars().all()
        assert len(active_sessions) == 1


@pytest.mark.asyncio
async def test_old_access_token_rejected_after_password_change(
    async_client: AsyncClient,
    api_session_factory,
    test_user: IamUser,
) -> None:
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert login.status_code == 200
    old_access_token = login.json()["data"]["access_token"]

    await _set_force_password_change(
        api_session_factory,
        user_id=test_user.id,
        force_password_change=True,
    )

    password_change_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert password_change_login.status_code == 200
    change_token = password_change_login.json()["data"]["password_change_token"]

    change = await async_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "NewPass123!"},
        headers={"Authorization": f"Bearer {change_token}", "Idempotency-Key": "pwd-change-old-access"},
    )
    assert change.status_code == 200
    new_access_token = change.json()["data"]["access_token"]

    old_me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert old_me.status_code == 401

    new_me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert new_me.status_code == 200


@pytest.mark.asyncio
async def test_password_change_idempotent_with_same_idempotency_key(
    async_client: AsyncClient,
    api_session_factory,
    test_user: IamUser,
) -> None:
    await _set_force_password_change(
        api_session_factory,
        user_id=test_user.id,
        force_password_change=True,
    )

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "TestPass123!"},
    )
    assert login.status_code == 200
    change_token = login.json()["data"]["password_change_token"]
    headers = {
        "Authorization": f"Bearer {change_token}",
        "Idempotency-Key": "pwd-change-idempotent",
    }

    first = await async_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "NewPass123!"},
        headers=headers,
    )
    assert first.status_code == 200

    second = await async_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "AnotherPass123!"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert second.json()["data"] == first.json()["data"]
