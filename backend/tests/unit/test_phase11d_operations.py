from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamSession, IamUser, UserRole


def _script_dir() -> ScriptDirectory:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini = backend_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return ScriptDirectory.from_config(cfg)


@pytest.mark.asyncio
async def test_phase11d_alembic_has_single_head() -> None:
    script_dir = _script_dir()
    heads = script_dir.get_heads()
    assert len(heads) == 1
    assert script_dir.get_current_head() == heads[0]


@pytest.mark.asyncio
async def test_phase11d_migration_import_safety() -> None:
    script_dir = _script_dir()
    for revision in script_dir.walk_revisions():
        assert revision.module is not None


async def _platform_admin_token(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> str:
    admin = IamUser(
        tenant_id=tenant_id,
        email=f"platform-admin-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Platform Admin",
        role=UserRole.platform_admin,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(admin)
    await async_session.flush()
    return create_access_token(admin.id, admin.tenant_id, admin.role.value)


@pytest.mark.asyncio
async def test_ops_migration_status_requires_platform_admin(
    async_client,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/platform/ops/migrations/status",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ops_migration_status_payload_for_admin(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin_token = await _platform_admin_token(async_session, tenant_id=test_tenant.id)
    response = await async_client.get(
        "/api/v1/platform/ops/migrations/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "status" in data
    assert "expected_head" in data
    assert "current_revision" in data
    assert "has_pending_migrations" in data
    assert "is_current_revision_known" in data


@pytest.mark.asyncio
async def test_ops_jobs_status_shape_for_admin(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin_token = await _platform_admin_token(async_session, tenant_id=test_tenant.id)
    response = await async_client.get(
        "/api/v1/platform/ops/jobs/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tenant_id"] == str(test_tenant.id)
    assert "jobs" in data
    assert "erp_sync_runs" in data["jobs"]
    assert "fx_revaluation_runs" in data["jobs"]
    assert "fx_translation_runs" in data["jobs"]
    assert "audit_export_runs" in data["jobs"]


@pytest.mark.asyncio
async def test_ops_session_status_counts_for_admin(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    now = datetime.now(UTC)
    session_user = IamUser(
        tenant_id=test_tenant.id,
        email=f"session-user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("SessionPass123!"),
        full_name="Session User",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(session_user)
    await async_session.flush()

    active = IamSession(
        user_id=session_user.id,
        tenant_id=test_tenant.id,
        refresh_token_hash=uuid.uuid4().hex,
        device_info="test-active",
        ip_address="127.0.0.1",
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
    )
    revoked = IamSession(
        user_id=session_user.id,
        tenant_id=test_tenant.id,
        refresh_token_hash=uuid.uuid4().hex,
        device_info="test-revoked",
        ip_address="127.0.0.1",
        expires_at=now + timedelta(hours=1),
        revoked_at=now - timedelta(minutes=1),
    )
    expired = IamSession(
        user_id=session_user.id,
        tenant_id=test_tenant.id,
        refresh_token_hash=uuid.uuid4().hex,
        device_info="test-expired",
        ip_address="127.0.0.1",
        expires_at=now - timedelta(minutes=1),
        revoked_at=None,
    )
    async_session.add_all([active, revoked, expired])
    await async_session.flush()

    admin_token = await _platform_admin_token(async_session, tenant_id=test_tenant.id)
    response = await async_client.get(
        "/api/v1/platform/ops/sessions/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["active_sessions"] >= 1
    assert data["revoked_sessions"] >= 1
    assert data["expired_sessions"] >= 1
    assert isinstance(data["recent_sessions"], list)


@pytest.mark.asyncio
async def test_ops_retry_missing_erp_run_returns_404(
    async_client,
    async_session: AsyncSession,
    test_tenant,
) -> None:
    admin_token = await _platform_admin_token(async_session, tenant_id=test_tenant.id)
    response = await async_client.post(
        f"/api/v1/platform/ops/jobs/erp-sync/{uuid.uuid4()}/retry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
