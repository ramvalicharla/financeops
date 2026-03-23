from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.backup.models import BackupRunLog
from financeops.modules.backup.service import (
    get_backup_status,
    log_backup_run,
    verify_database_integrity,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/backup", tags=["backup"])


class BackupLogRequest(BaseModel):
    backup_type: str
    status: str
    triggered_by: str
    size_bytes: int | None = None
    backup_location: str | None = None
    verification_passed: bool | None = None
    error_message: str | None = None
    retention_days: int = 30


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _serialize_backup_row(row: BackupRunLog) -> dict[str, str | int | bool | None]:
    return {
        "id": str(row.id),
        "backup_type": row.backup_type,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "size_bytes": row.size_bytes,
        "backup_location": row.backup_location,
        "verification_passed": row.verification_passed,
        "error_message": row.error_message,
        "triggered_by": row.triggered_by,
        "retention_days": row.retention_days,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/status")
async def backup_status(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    payload = await get_backup_status(session)
    return {
        "last_full_backup": payload["last_full_backup"].isoformat() if payload["last_full_backup"] else None,
        "last_full_backup_age_hours": (
            format(payload["last_full_backup_age_hours"], "f")
            if isinstance(payload["last_full_backup_age_hours"], Decimal)
            else None
        ),
        "last_verified_restore": payload["last_verified_restore"].isoformat() if payload["last_verified_restore"] else None,
        "is_backup_overdue": payload["is_backup_overdue"],
        "recent_runs": [_serialize_backup_row(row) for row in payload["recent_runs"]],
        "rag_status": payload["rag_status"],
    }


@router.post("/log")
async def backup_log(
    body: BackupLogRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = await log_backup_run(
        session,
        backup_type=body.backup_type,
        status=body.status,
        triggered_by=body.triggered_by,
        size_bytes=body.size_bytes,
        backup_location=body.backup_location,
        verification_passed=body.verification_passed,
        error_message=body.error_message,
        retention_days=body.retention_days,
    )
    await session.flush()
    return _serialize_backup_row(row)


@router.get("/runs", response_model=Paginated[dict])
async def backup_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    total = (await session.execute(select(BackupRunLog.id))).scalars().all()
    rows = (
        await session.execute(
            select(BackupRunLog)
            .order_by(BackupRunLog.started_at.desc(), BackupRunLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_backup_row(row) for row in rows],
        total=len(total),
        limit=limit,
        offset=offset,
    )


@router.post("/verify-integrity")
async def backup_verify_integrity(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    payload = await verify_database_integrity(session)
    return payload
