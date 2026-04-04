from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.backup.service import (
    get_backup_status,
    log_backup_run,
    verify_database_integrity,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_super_admin(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email="backup-admin@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Backup Admin",
        role=UserRole.super_admin,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


def test_backup_scripts_exist() -> None:
    base = Path(__file__).resolve().parents[2] / "scripts" / "backup"
    for filename in ["backup_postgres.sh", "restore_postgres.sh", "verify_restore.sh", "backup_redis.sh", "README.md"]:
        assert (base / filename).exists(), f"Missing backup file: {filename}"


def test_readme_has_rto_rpo() -> None:
    readme = (Path(__file__).resolve().parents[2] / "scripts" / "backup" / "README.md").read_text(encoding="utf-8")
    assert "RTO" in readme
    assert "RPO" in readme


def test_backup_scripts_have_set_euo_pipefail() -> None:
    base = Path(__file__).resolve().parents[2] / "scripts" / "backup"
    for filename in ["backup_postgres.sh", "restore_postgres.sh", "verify_restore.sh", "backup_redis.sh"]:
        body = (base / filename).read_text(encoding="utf-8")
        assert "set -euo pipefail" in body


@pytest.mark.asyncio
async def test_log_backup_run_creates_record(async_session: AsyncSession) -> None:
    row = await log_backup_run(
        async_session,
        backup_type="full",
        status="completed",
        triggered_by="manual",
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_backup_run_log_is_append_only(async_session: AsyncSession) -> None:
    row = await log_backup_run(
        async_session,
        backup_type="full",
        status="completed",
        triggered_by="manual",
    )

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("backup_run_log")))
    await async_session.execute(text(create_trigger_sql("backup_run_log")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE backup_run_log SET status = 'failed' WHERE id = :id"),
            {"id": row.id},
        )


@pytest.mark.asyncio
async def test_backup_status_no_runs_is_overdue(async_session: AsyncSession) -> None:
    payload = await get_backup_status(async_session)
    assert payload["is_backup_overdue"] is True


@pytest.mark.asyncio
async def test_recent_backup_rag_green(async_session: AsyncSession) -> None:
    await log_backup_run(async_session, backup_type="full", status="completed", triggered_by="scheduled")
    await log_backup_run(
        async_session,
        backup_type="full",
        status="verified",
        triggered_by="manual",
        verification_passed=True,
    )
    payload = await get_backup_status(async_session)
    assert payload["rag_status"] == "green"


@pytest.mark.asyncio
async def test_old_backup_rag_red(async_session: AsyncSession) -> None:
    await log_backup_run(
        async_session,
        backup_type="full",
        status="completed",
        triggered_by="scheduled",
        started_at=datetime.now(UTC) - timedelta(hours=60),
    )
    payload = await get_backup_status(async_session)
    assert payload["rag_status"] == "red"


@pytest.mark.asyncio
async def test_verify_integrity_passes_on_healthy_db(async_session: AsyncSession, test_tenant, test_user) -> None:
    await async_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS _backup_rls_probe (
              id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
              tenant_id uuid NOT NULL
            )
            """
        )
    )
    await async_session.execute(text("ALTER TABLE _backup_rls_probe ENABLE ROW LEVEL SECURITY"))
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = '_backup_rls_probe'
                  AND policyname = 'tenant_isolation'
              ) THEN
                CREATE POLICY tenant_isolation ON _backup_rls_probe USING (true);
              END IF;
            END $$;
            """
        )
    )

    script_dir = ScriptDirectory.from_config(Config("alembic.ini"))
    expected_head = script_dir.get_current_head()
    await async_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num varchar(32) NOT NULL)"))
    await async_session.execute(text("DELETE FROM alembic_version"))
    await async_session.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
        {"version_num": expected_head},
    )

    payload = await verify_database_integrity(async_session)
    assert payload["passed"] is True


@pytest.mark.asyncio
async def test_integrity_has_rls_check(async_session: AsyncSession) -> None:
    payload = await verify_database_integrity(async_session)
    assert "rls_policies" in payload["checks"]


@pytest.mark.asyncio
async def test_integrity_has_alembic_check(async_session: AsyncSession) -> None:
    payload = await verify_database_integrity(async_session)
    assert "alembic_head" in payload["checks"]


@pytest.mark.asyncio
async def test_integrity_result_structure(async_session: AsyncSession) -> None:
    payload = await verify_database_integrity(async_session)
    assert "passed" in payload
    assert "checks" in payload


@pytest.mark.asyncio
async def test_backup_status_endpoint(async_session: AsyncSession, async_client, test_user: IamUser) -> None:
    admin = await _create_super_admin(async_session, tenant_id=test_user.tenant_id)
    response = await async_client.get(
        "/api/v1/backup/status",
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    assert "rag_status" in response.json()["data"]


@pytest.mark.asyncio
async def test_backup_status_requires_platform_admin(async_client, test_user: IamUser) -> None:
    response = await async_client.get(
        "/api/v1/backup/status",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_integrity_verify_endpoint(async_session: AsyncSession, async_client, test_user: IamUser) -> None:
    admin = await _create_super_admin(async_session, tenant_id=test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/backup/verify-integrity",
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "passed" in payload
    assert "checks" in payload
