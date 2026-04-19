from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamSession, IamUser, UserRole
from financeops.modules.notifications.models import NotificationEvent
from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.services.rbac.permission_service import create_permission, grant_role_permission
from financeops.platform.services.rbac.role_service import (
    assign_user_role_now,
    create_role,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)


def _disable_pytest_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    original_getenv = os.getenv

    def _fake_getenv(key: str, default: str | None = None) -> str | None:
        if key == "PYTEST_CURRENT_TEST":
            return ""
        return original_getenv(key, default)

    monkeypatch.setattr("financeops.modules.notifications.service.os.getenv", _fake_getenv)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_same_tenant_user(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: UserRole = UserRole.read_only,
    is_active: bool = True,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Managed User",
        role=role,
        is_active=is_active,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return user


async def _create_other_tenant_user(async_session: AsyncSession) -> IamUser:
    tenant_id = uuid.uuid4()
    tenant_payload = {
        "display_name": "Other Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(tenant_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    async_session.add(tenant)
    await async_session.flush()
    return await _create_same_tenant_user(
        async_session,
        tenant_id=tenant.id,
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
    )


async def _seed_deny_permission(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    resource_type: str,
    action: str,
) -> None:
    permission = (
        await async_session.execute(
            select(CpPermission).where(
                CpPermission.resource_type == resource_type,
                CpPermission.action == action,
            )
        )
    ).scalars().first()
    if permission is None:
        permission = await create_permission(
            async_session,
            actor_tenant_id=tenant_id,
            actor_user_id=user_id,
            permission_code=f"{resource_type}.{action}.{uuid.uuid4().hex[:8]}",
            resource_type=resource_type,
            action=action,
            description="test deny permission",
        )
    role = await create_role(
        async_session,
        tenant_id=tenant_id,
        role_code=f"deny-{resource_type}-{uuid.uuid4().hex[:6]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="corr-user-management",
    )
    await grant_role_permission(
        async_session,
        tenant_id=tenant_id,
        role_id=role.id,
        permission_id=permission.id,
        effect="deny",
        actor_user_id=user_id,
        correlation_id="corr-user-management",
    )
    await assign_user_role_now(
        async_session,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role.id,
        context_type="tenant",
        context_id=tenant_id,
        assigned_by=user_id,
        actor_user_id=user_id,
        correlation_id="corr-user-management",
    )
    await async_session.flush()


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
) -> IamUser:
    await _ensure_platform_tenant(session)
    user = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform User",
        role=role,
        is_active=True,
        mfa_enabled=True,
        force_mfa_setup=False,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_list_users_returns_tenant_scoped_results(
    async_client,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    local_user = await _create_same_tenant_user(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        email=f"list-local-{uuid.uuid4().hex[:8]}@example.com",
    )
    other_user = await _create_other_tenant_user(api_db_session)

    response = await async_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    emails = {row["email"] for row in payload["users"]}
    assert api_test_user.email in emails
    assert local_user.email in emails
    assert other_user.email not in emails


@pytest.mark.asyncio
async def test_invite_user_triggers_async_notification_not_sync_smtp(
    async_client,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_pytest_inline(monkeypatch)
    scheduled: list[tuple[str, str]] = []

    def _fake_schedule_notification_delivery(*, notification_event_id, tenant_id):  # type: ignore[no-untyped-def]
        scheduled.append((str(notification_event_id), str(tenant_id)))

    monkeypatch.setattr(
        "financeops.modules.notifications.tasks.schedule_notification_delivery",
        _fake_schedule_notification_delivery,
    )

    response = await async_client.post(
        "/api/v1/users",
        headers={
            "Authorization": f"Bearer {api_test_access_token}",
            "Idempotency-Key": "user-invite-idem-1",
        },
        json={
            "email": f"invite-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Invited User",
            "role": "read_only",
            "entity_ids": [],
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    event = (
        await api_db_session.execute(
            select(NotificationEvent).where(
                NotificationEvent.tenant_id == api_test_user.tenant_id,
                NotificationEvent.recipient_user_id == uuid.UUID(payload["user_id"]),
                NotificationEvent.notification_type == "user_invited",
            )
        )
    ).scalar_one_or_none()
    assert event is not None
    assert scheduled == [(str(event.id), str(api_test_user.tenant_id))]
    assert "queued" in payload["message"].lower()
    await api_db_session.commit()


@pytest.mark.asyncio
async def test_update_role_requires_users_manage_roles_permission(
    async_client,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    target = await _create_same_tenant_user(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        email=f"role-target-{uuid.uuid4().hex[:8]}@example.com",
    )
    await _seed_deny_permission(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        user_id=api_test_user.id,
        resource_type="tenant_user",
        action="manage",
    )

    response = await async_client.patch(
        f"/api/v1/users/{target.id}/role",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={"role": "finance_team"},
    )

    assert response.status_code == 403
    assert "tenant_user.manage denied" in response.text


@pytest.mark.asyncio
async def test_offboard_user_revokes_sessions_and_marks_inactive(
    async_client,
    api_db_session: AsyncSession,
    api_test_access_token: str,
    api_test_user: IamUser,
) -> None:
    target = await _create_same_tenant_user(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        email=f"offboard-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_team,
    )
    session_row = IamSession(
        user_id=target.id,
        tenant_id=target.tenant_id,
        refresh_token_hash=uuid.uuid4().hex,
        device_info="test-device",
        ip_address="127.0.0.1",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
    )
    api_db_session.add(session_row)
    await api_db_session.flush()

    response = await async_client.delete(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sessions_revoked"] == 1

    target_id = target.id
    session_row_id = session_row.id
    api_db_session.expire_all()
    refreshed_user = (
        await api_db_session.execute(select(IamUser).where(IamUser.id == target_id))
    ).scalar_one()
    refreshed_session = (
        await api_db_session.execute(select(IamSession).where(IamSession.id == session_row_id))
    ).scalar_one()
    assert refreshed_user.is_active is False
    assert refreshed_session.revoked_at is not None
    await api_db_session.commit()


@pytest.mark.asyncio
async def test_cannot_assign_platform_owner_without_platform_owner_role(
    async_client,
    api_db_session: AsyncSession,
) -> None:
    super_admin = await _create_platform_user(
        api_db_session,
        email=f"super-admin-{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.super_admin,
    )

    response = await async_client.post(
        "/api/v1/platform/users",
        headers=_auth_headers(super_admin),
        json={
            "email": f"platform-admin-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Platform Admin",
            "role": "platform_admin",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Only platform_owner can assign this role"


@pytest.mark.asyncio
async def test_get_user_returns_404_for_different_tenant_user(
    async_client,
    api_db_session: AsyncSession,
    api_test_access_token: str,
) -> None:
    other_user = await _create_other_tenant_user(api_db_session)

    response = await async_client.get(
        f"/api/v1/users/{other_user.id}",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )

    assert response.status_code == 404
