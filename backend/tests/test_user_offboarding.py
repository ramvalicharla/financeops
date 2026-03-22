from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamSession, IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.services.user_service import offboard_user
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: UserRole = UserRole.finance_team,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Offboard Target",
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_finance_leader(session: AsyncSession, tenant_id: uuid.UUID) -> IamUser:
    return await _create_user(
        session,
        tenant_id=tenant_id,
        email=f"leader_{uuid.uuid4().hex[:10]}@example.com",
        role=UserRole.finance_leader,
    )


async def _create_tenant(session: AsyncSession) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": f"Tenant-{tenant_id.hex[:8]}",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=record_data["display_name"],
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _create_sessions(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    count: int,
) -> None:
    for _ in range(count):
        session.add(
            IamSession(
                user_id=user_id,
                tenant_id=tenant_id,
                refresh_token_hash=uuid.uuid4().hex,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    await session.flush()


@pytest.mark.asyncio
async def test_offboard_revokes_all_sessions(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Offboarding revokes every active session for the user."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"offboard_{uuid.uuid4().hex[:8]}@example.com",
    )
    await _create_sessions(
        async_session,
        user_id=target.id,
        tenant_id=test_tenant.id,
        count=3,
    )
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Left organization"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["sessions_revoked"] == 3
    remaining = (
        await async_session.execute(
            text("SELECT COUNT(*) FROM iam_sessions WHERE user_id = CAST(:id AS uuid)"),
            {"id": str(target.id)},
        )
    ).scalar_one()
    assert remaining == 0


@pytest.mark.asyncio
async def test_offboard_disables_user(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Offboarded user cannot authenticate."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target_email = f"off_login_{uuid.uuid4().hex[:8]}@example.com"
    target = await _create_user(async_session, tenant_id=test_tenant.id, email=target_email)
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Access removed"},
    )
    assert response.status_code == 200
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "TestPass123!"},
    )
    assert login_response.status_code == 401


@pytest.mark.asyncio
async def test_offboard_creates_audit_record(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Offboarding writes a user.offboarded audit event."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"audit_off_{uuid.uuid4().hex[:8]}@example.com",
    )
    reason = "Policy violation"
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": reason},
    )
    assert response.status_code == 200
    audit = (
        await async_session.execute(
            text(
                """
                SELECT action, resource_id
                FROM audit_trail
                WHERE action = 'user.offboarded'
                  AND resource_id = :resource_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"resource_id": str(target.id)},
        )
    ).first()
    assert audit is not None
    assert audit[0] == "user.offboarded"


@pytest.mark.asyncio
async def test_offboard_is_atomic(async_session: AsyncSession, test_tenant: IamTenant, monkeypatch: pytest.MonkeyPatch) -> None:
    """If audit log write fails, no partial offboard occurs."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"atomic_off_{uuid.uuid4().hex[:8]}@example.com",
    )
    target_id = target.id
    await _create_sessions(async_session, user_id=target.id, tenant_id=test_tenant.id, count=2)
    await async_session.commit()
    await set_tenant_context(async_session, test_tenant.id)

    async def _boom(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr("financeops.services.user_service.log_action", _boom)

    with pytest.raises(RuntimeError):
        await offboard_user(
            async_session,
            tenant_id=test_tenant.id,
            user_id=target_id,
            offboarded_by=actor.id,
            reason="Atomicity test",
        )
    await async_session.rollback()

    user_row = (
        await async_session.execute(
            text("SELECT is_active FROM iam_users WHERE id = CAST(:id AS uuid)"),
            {"id": str(target_id)},
        )
    ).scalar_one()
    assert user_row is True
    session_count = (
        await async_session.execute(
            text("SELECT COUNT(*) FROM iam_sessions WHERE user_id = CAST(:id AS uuid)"),
            {"id": str(target_id)},
        )
    ).scalar_one()
    assert session_count == 2


@pytest.mark.asyncio
async def test_offboard_wrong_tenant_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Cannot offboard a user from a different tenant."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    foreign_tenant = await _create_tenant(async_session)
    await set_tenant_context(async_session, foreign_tenant.id)
    foreign_user = await _create_user(
        async_session,
        tenant_id=foreign_tenant.id,
        email=f"foreign_{uuid.uuid4().hex[:8]}@example.com",
    )
    response = await async_client.post(
        f"/api/v1/users/{foreign_user.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Cross-tenant should fail"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_offboard_already_inactive_returns_422(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Cannot offboard an already inactive user."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"inactive_{uuid.uuid4().hex[:8]}@example.com",
    )
    target.is_active = False
    await async_session.flush()
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Already inactive"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_offboard_requires_elevated_role(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Finance team role cannot offboard users."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"actor_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.finance_team,
    )
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"target_{uuid.uuid4().hex[:8]}@example.com",
    )
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Forbidden"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_offboard_clears_totp_secret(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Offboarding clears TOTP secret and disables MFA."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"totp_{uuid.uuid4().hex[:8]}@example.com",
    )
    await async_session.execute(
        text(
            """
            UPDATE iam_users
            SET totp_secret_encrypted = 'dummy',
                mfa_enabled = true
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"id": str(target.id)},
    )
    await async_session.flush()
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "MFA revoke"},
    )
    assert response.status_code == 200
    row = (
        await async_session.execute(
            text("SELECT mfa_enabled, totp_secret_encrypted FROM iam_users WHERE id = CAST(:id AS uuid)"),
            {"id": str(target.id)},
        )
    ).one()
    assert row[0] is False
    assert row[1] is None


@pytest.mark.asyncio
async def test_offboard_service_unknown_user(async_session: AsyncSession, test_tenant: IamTenant) -> None:
    """Service rejects unknown user."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    with pytest.raises(Exception):
        await offboard_user(
            async_session,
            tenant_id=test_tenant.id,
            user_id=uuid.uuid4(),
            offboarded_by=actor.id,
            reason="Unknown",
        )


@pytest.mark.asyncio
async def test_offboard_response_contains_counts(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant: IamTenant,
) -> None:
    """Offboard response includes session and grant counters."""
    await set_tenant_context(async_session, test_tenant.id)
    actor = await _create_finance_leader(async_session, test_tenant.id)
    token = create_access_token(actor.id, actor.tenant_id, actor.role.value)
    target = await _create_user(
        async_session,
        tenant_id=test_tenant.id,
        email=f"counts_{uuid.uuid4().hex[:8]}@example.com",
    )
    await _create_sessions(async_session, user_id=target.id, tenant_id=test_tenant.id, count=1)
    response = await async_client.post(
        f"/api/v1/users/{target.id}/offboard",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Count check"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "sessions_revoked" in payload
    assert "grants_revoked" in payload
