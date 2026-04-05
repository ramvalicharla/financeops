from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.services.auth_service import setup_totp, verify_totp_setup
from financeops.seed.platform_owner import SeedAccount, seed_platform_users
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _ensure_platform_tenant(session: AsyncSession) -> IamTenant:
    tenant = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == PLATFORM_TENANT_ID)
        )
    ).scalar_one_or_none()
    if tenant is not None:
        return tenant

    record_data = {
        "display_name": "FinanceOps Platform",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    platform_tenant = IamTenant(
        id=PLATFORM_TENANT_ID,
        tenant_id=PLATFORM_TENANT_ID,
        display_name="FinanceOps Platform",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        is_platform_tenant=True,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(platform_tenant)
    await session.flush()
    return platform_tenant


async def _create_platform_user(
    session: AsyncSession,
    *,
    email: str,
    role: UserRole,
    force_mfa_setup: bool = False,
) -> IamUser:
    await _ensure_platform_tenant(session)
    user = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform User",
        role=role,
        is_active=True,
        mfa_enabled=False,
        force_mfa_setup=force_mfa_setup,
    )
    session.add(user)
    await session.flush()
    return user


def _load_seed_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_platform_owner.py"
    spec = importlib.util.spec_from_file_location("seed_platform_owner", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load seed_platform_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_platform_tenant_exists_after_migration(async_client, async_session: AsyncSession) -> None:
    _ = async_client
    await _ensure_platform_tenant(async_session)
    row = (
        await async_session.execute(
            text(
                """
                SELECT is_platform_tenant
                FROM iam_tenants
                WHERE id = CAST(:tenant_id AS uuid)
                """
            ),
            {"tenant_id": str(PLATFORM_TENANT_ID)},
        )
    ).first()
    assert row is not None
    assert bool(row[0]) is True


@pytest.mark.asyncio
async def test_force_mfa_setup_column_exists(async_session: AsyncSession) -> None:
    row = (
        await async_session.execute(
            text(
                """
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'iam_users'
                  AND column_name = 'force_mfa_setup'
                """
            )
        )
    ).first()
    assert row is not None
    default_text = str(row[0] or "").lower()
    assert "false" in default_text


@pytest.mark.asyncio
async def test_seed_script_idempotent(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_seed_module()

    class _SessionFactory:
        def __call__(self):
            class _SessionContext:
                async def __aenter__(self_nonlocal):
                    return async_session

                async def __aexit__(self_nonlocal, exc_type, exc, tb):
                    return False

            return _SessionContext()

    monkeypatch.setenv("PLATFORM_OWNER_EMAIL", "seed.owner@example.com")
    monkeypatch.setenv("PLATFORM_OWNER_PASSWORD", "SeedPass123!")
    monkeypatch.setenv("PLATFORM_OWNER_NAME", "Seed Owner")
    monkeypatch.setattr(module, "AsyncSessionLocal", _SessionFactory())
    original_commit = async_session.commit
    async_session.commit = async_session.flush  # type: ignore[method-assign]

    try:
        first = await module.seed_platform_owner()
        second = await module.seed_platform_owner()
        assert first == 0
        assert second == 0

        count = (
            await async_session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM iam_users
                    WHERE role = 'platform_owner'
                    """
                )
            )
        ).scalar_one()
        assert int(count) == 1
    finally:
        async_session.commit = original_commit  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_seed_platform_users_preserves_existing_auth_state(
    async_session: AsyncSession,
) -> None:
    await _ensure_platform_tenant(async_session)
    existing = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email="seed.preserve@example.com",
        hashed_password=hash_password("OriginalPass123!"),
        full_name="Original Name",
        role=UserRole.platform_admin,
        is_active=True,
        is_verified=True,
        mfa_enabled=True,
        force_password_change=False,
        force_mfa_setup=False,
    )
    async_session.add(existing)
    await async_session.flush()

    original_hash = existing.hashed_password

    class _SessionFactory:
        def __call__(self):
            class _SessionContext:
                async def __aenter__(self_nonlocal):
                    return async_session

                async def __aexit__(self_nonlocal, exc_type, exc, tb):
                    return False

            return _SessionContext()

    result = await seed_platform_users(
        [
            SeedAccount(
                email="seed.preserve@example.com",
                password="SeedPass123!",
                full_name="Updated Name",
                role=UserRole.platform_support,
            )
        ],
        session_factory=_SessionFactory(),
    )

    assert result["status"] == "seeded"
    await async_session.refresh(existing)
    assert existing.hashed_password == original_hash
    assert existing.mfa_enabled is True
    assert existing.force_password_change is False
    assert existing.force_mfa_setup is False
    assert existing.full_name == "Updated Name"
    assert existing.role == UserRole.platform_support


@pytest.mark.asyncio
async def test_create_platform_admin(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.create.admin@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.post(
        "/api/v1/platform/users",
        headers=_auth_headers(owner),
        json={
            "email": "admin.one@example.com",
            "full_name": "Admin One",
            "role": "platform_admin",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["role"] == "platform_admin"
    assert data["force_mfa_setup"] is True


@pytest.mark.asyncio
async def test_create_platform_user_requires_platform_owner(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await _ensure_platform_tenant(async_session)
    response = await async_client.post(
        "/api/v1/platform/users",
        headers=_auth_headers(test_user),
        json={
            "email": "admin.forbidden@example.com",
            "full_name": "Forbidden",
            "role": "platform_admin",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_platform_users(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.list@example.com",
        role=UserRole.platform_owner,
    )
    await _create_platform_user(
        async_session,
        email="support.list@example.com",
        role=UserRole.platform_support,
    )
    response = await async_client.get(
        "/api/v1/platform/users?limit=20&offset=0",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 2
    assert payload["limit"] == 20
    assert payload["offset"] == 0
    emails = {row["email"] for row in payload["data"]}
    assert test_user.email not in emails


@pytest.mark.asyncio
async def test_cannot_change_own_role(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.selfrole@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.patch(
        f"/api/v1/platform/users/{owner.id}/role",
        headers=_auth_headers(owner),
        json={"role": "platform_admin"},
    )
    assert response.status_code == 422
    assert "cannot change own role" in response.text


@pytest.mark.asyncio
async def test_cannot_remove_last_platform_owner(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.lastdemote@example.com",
        role=UserRole.platform_owner,
    )
    actor = await _create_platform_user(
        async_session,
        email="superadmin.lastdemote@example.com",
        role=UserRole.super_admin,
    )
    await async_session.execute(
        text(
            """
            UPDATE iam_users
            SET role = 'platform_admin'
            WHERE role = 'platform_owner'
              AND id <> CAST(:owner_id AS uuid)
            """
        ),
        {"owner_id": str(owner.id)},
    )
    await async_session.flush()
    response = await async_client.patch(
        f"/api/v1/platform/users/{owner.id}/role",
        headers=_auth_headers(actor),
        json={"role": "platform_admin"},
    )
    assert response.status_code == 422
    assert "cannot demote last platform_owner" in response.text


@pytest.mark.asyncio
async def test_cannot_deactivate_yourself(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.selfdeactivate@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.delete(
        f"/api/v1/platform/users/{owner.id}",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 422
    assert "cannot deactivate yourself" in response.text


@pytest.mark.asyncio
async def test_cannot_deactivate_last_platform_owner(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.lastdeactivate@example.com",
        role=UserRole.platform_owner,
    )
    actor = await _create_platform_user(
        async_session,
        email="superadmin.lastdeactivate@example.com",
        role=UserRole.super_admin,
    )
    await async_session.execute(
        text(
            """
            UPDATE iam_users
            SET role = 'platform_admin'
            WHERE role = 'platform_owner'
              AND id <> CAST(:owner_id AS uuid)
            """
        ),
        {"owner_id": str(owner.id)},
    )
    await async_session.flush()
    response = await async_client.delete(
        f"/api/v1/platform/users/{owner.id}",
        headers=_auth_headers(actor),
    )
    assert response.status_code == 422
    assert "cannot deactivate last platform_owner" in response.text


@pytest.mark.asyncio
async def test_deactivate_platform_admin(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.deactivateadmin@example.com",
        role=UserRole.platform_owner,
    )
    admin = await _create_platform_user(
        async_session,
        email="admin.deactivate@example.com",
        role=UserRole.platform_admin,
    )
    response = await async_client.delete(
        f"/api/v1/platform/users/{admin.id}",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_platform_users_isolated_from_tenants(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    owner = await _create_platform_user(
        async_session,
        email="owner.isolation@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.get(
        "/api/v1/platform/users",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    emails = {row["email"] for row in payload["data"]}
    assert test_user.email not in emails


@pytest.mark.asyncio
async def test_login_returns_requires_mfa_setup_when_forced(
    async_client,
    async_session: AsyncSession,
) -> None:
    user = await _create_platform_user(
        async_session,
        email="forced.mfa@example.com",
        role=UserRole.platform_admin,
        force_mfa_setup=True,
    )
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["requires_mfa_setup"] is True
    assert isinstance(data.get("setup_token"), str)
    assert "access_token" not in data


@pytest.mark.asyncio
async def test_login_normal_when_mfa_setup_not_forced(
    async_client,
    async_session: AsyncSession,
) -> None:
    user = await _create_platform_user(
        async_session,
        email="normal.mfa@example.com",
        role=UserRole.platform_admin,
        force_mfa_setup=False,
    )
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_force_mfa_setup_cleared_after_setup(async_session: AsyncSession) -> None:
    user = await _create_platform_user(
        async_session,
        email="mfa.clear@example.com",
        role=UserRole.platform_admin,
        force_mfa_setup=True,
    )
    setup_payload = await setup_totp(user, async_session)
    totp_code = pyotp.TOTP(setup_payload["totp_secret"]).now()
    confirmed = await verify_totp_setup(user, totp_code, async_session)

    assert confirmed is True
    assert user.mfa_enabled is True
    assert user.force_mfa_setup is False
