from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.backup.models import BackupRunLog


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def log_backup_run(
    session: AsyncSession,
    backup_type: str,
    status: str,
    triggered_by: str,
    size_bytes: int | None = None,
    backup_location: str | None = None,
    verification_passed: bool | None = None,
    error_message: str | None = None,
    retention_days: int = 30,
) -> BackupRunLog:
    entry = BackupRunLog(
        backup_type=backup_type,
        status=status,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if status in {"completed", "failed", "verified"} else None,
        size_bytes=size_bytes,
        backup_location=backup_location,
        verification_passed=verification_passed,
        error_message=error_message,
        triggered_by=triggered_by,
        retention_days=retention_days,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_backup_status(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    recent = (
        await session.execute(
            select(BackupRunLog).order_by(BackupRunLog.started_at.desc()).limit(10)
        )
    ).scalars().all()

    last_full = (
        await session.execute(
            select(BackupRunLog)
            .where(
                BackupRunLog.backup_type == "full",
                BackupRunLog.status.in_(("completed", "verified")),
            )
            .order_by(BackupRunLog.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_verified = (
        await session.execute(
            select(BackupRunLog)
            .where(
                BackupRunLog.status == "verified",
                BackupRunLog.verification_passed.is_(True),
            )
            .order_by(BackupRunLog.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_failed_verify = (
        await session.execute(
            select(BackupRunLog)
            .where(
                BackupRunLog.status == "verified",
                BackupRunLog.verification_passed.is_(False),
            )
            .order_by(BackupRunLog.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    last_full_dt = last_full.started_at if last_full else None
    age_hours: Decimal | None = None
    if last_full_dt is not None:
        age_hours = _q2(Decimal(str((now - last_full_dt).total_seconds() / 3600)))

    is_backup_overdue = age_hours is None or age_hours > Decimal("48")

    rag_status = "red"
    if age_hours is not None and age_hours < Decimal("25") and last_verified is not None:
        rag_status = "green"
    elif (age_hours is not None and age_hours < Decimal("48")) or (
        last_verified is None or (now - last_verified.started_at) > timedelta(days=7)
    ):
        rag_status = "amber"
    if is_backup_overdue or (last_failed_verify is not None and last_verified is None):
        rag_status = "red"

    return {
        "last_full_backup": last_full_dt,
        "last_full_backup_age_hours": age_hours,
        "last_verified_restore": last_verified.started_at if last_verified else None,
        "is_backup_overdue": is_backup_overdue,
        "recent_runs": list(recent),
        "rag_status": rag_status,
    }


async def verify_database_integrity(session: AsyncSession) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    # 1) alembic head matches version table
    alembic_cfg = Config("alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script_dir.get_current_head()
    current_head = (
        await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    ).scalar_one_or_none()
    checks["alembic_head"] = current_head == expected_head

    # 2) RLS policies are present
    policy_count = (
        await session.execute(text("SELECT count(*) FROM pg_policies"))
    ).scalar_one()
    checks["rls_policies"] = int(policy_count or 0) > 0

    # 3) chain verifier importable
    try:
        from financeops.utils.chain_hash import verify_chain  # noqa: F401

        checks["chain_hash_import"] = True
    except Exception:
        checks["chain_hash_import"] = False

    # 4) key table row counts non-zero
    tenants_count = (await session.execute(text("SELECT count(*) FROM iam_tenants"))).scalar_one()
    users_count = (await session.execute(text("SELECT count(*) FROM iam_users"))).scalar_one()
    checks["key_row_counts"] = int(tenants_count or 0) > 0 and int(users_count or 0) > 0

    return {"passed": all(checks.values()), "checks": checks}
