from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_platform_admin
from financeops.api.v1 import health as health_api
from financeops.db.models.erp_sync import ExternalSyncRun
from financeops.db.models.fx_ias21 import (
    AccountingFxRevaluationRun,
    ConsolidationTranslationRun,
)
from financeops.db.models.accounting_notifications import AccountingAuditExportRun
from financeops.db.models.users import IamSession, IamUser
from financeops.modules.erp_sync.application.sync_service import SyncService
from financeops.shared_kernel.response import ok

router = APIRouter()

_RETRYABLE_ERP_SYNC_STATUSES = {"paused"}


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[4]
    alembic_ini = backend_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return cfg


def _compute_pending_revisions(script_dir: ScriptDirectory, *, current: str | None, expected: str | None) -> list[str]:
    if not current or not expected or current == expected:
        return []
    revisions: list[str] = []
    try:
        for revision in script_dir.iterate_revisions(expected, current):
            if revision.revision != current:
                revisions.append(str(revision.revision))
    except Exception:
        return []
    return revisions


async def _migration_status_payload(session: AsyncSession) -> dict[str, Any]:
    script_dir = ScriptDirectory.from_config(_alembic_config())
    heads = [str(head) for head in script_dir.get_heads()]
    expected_head = script_dir.get_current_head()

    current_revision: str | None = None
    read_error: str | None = None
    try:
        current_revision = (
            await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        ).scalar_one_or_none()
    except Exception as exc:
        read_error = str(exc) or exc.__class__.__name__

    known_revision = False
    if current_revision is not None:
        try:
            known_revision = script_dir.get_revision(current_revision) is not None
        except Exception:
            known_revision = False
    has_pending = bool(
        current_revision
        and expected_head
        and current_revision != expected_head
    )
    has_head_divergence = len(heads) > 1

    if read_error:
        status_value = "error"
    elif not known_revision and current_revision is not None:
        status_value = "error"
    elif has_pending or has_head_divergence:
        status_value = "warning"
    else:
        status_value = "ok"

    pending_revisions = _compute_pending_revisions(
        script_dir,
        current=current_revision,
        expected=expected_head,
    )

    return {
        "status": status_value,
        "expected_head": expected_head,
        "known_heads": heads,
        "current_revision": current_revision,
        "is_head_consistent": bool(current_revision and expected_head and current_revision == expected_head),
        "has_pending_migrations": has_pending,
        "has_divergent_heads": has_head_divergence,
        "is_current_revision_known": known_revision,
        "pending_revisions": pending_revisions,
        "read_error": read_error,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def _status_counts(rows: list[tuple[str | None, int]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status_value, row_count in rows:
        key = (status_value or "UNKNOWN").upper()
        counts[key] = int(row_count)
    return counts


async def _ops_job_status_payload(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lookback_hours: int,
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(hours=lookback_hours)

    erp_rows = (
        await session.execute(
            select(ExternalSyncRun.run_status, func.count(ExternalSyncRun.id))
            .where(
                ExternalSyncRun.tenant_id == tenant_id,
                ExternalSyncRun.created_at >= since,
            )
            .group_by(ExternalSyncRun.run_status)
        )
    ).all()
    revaluation_rows = (
        await session.execute(
            select(AccountingFxRevaluationRun.status, func.count(AccountingFxRevaluationRun.id))
            .where(
                AccountingFxRevaluationRun.tenant_id == tenant_id,
                AccountingFxRevaluationRun.created_at >= since,
            )
            .group_by(AccountingFxRevaluationRun.status)
        )
    ).all()
    translation_rows = (
        await session.execute(
            select(ConsolidationTranslationRun.status, func.count(ConsolidationTranslationRun.id))
            .where(
                ConsolidationTranslationRun.tenant_id == tenant_id,
                ConsolidationTranslationRun.created_at >= since,
            )
            .group_by(ConsolidationTranslationRun.status)
        )
    ).all()
    audit_export_rows = (
        await session.execute(
            select(AccountingAuditExportRun.status, func.count(AccountingAuditExportRun.id))
            .where(
                AccountingAuditExportRun.tenant_id == tenant_id,
                AccountingAuditExportRun.created_at >= since,
            )
            .group_by(AccountingAuditExportRun.status)
        )
    ).all()

    retryable_erp_runs = int(
        (
            await session.execute(
                select(func.count(ExternalSyncRun.id)).where(
                    ExternalSyncRun.tenant_id == tenant_id,
                    ExternalSyncRun.created_at >= since,
                    ExternalSyncRun.run_status.in_(_RETRYABLE_ERP_SYNC_STATUSES),
                    ExternalSyncRun.is_resumable.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    return {
        "tenant_id": str(tenant_id),
        "lookback_hours": lookback_hours,
        "window_start": since.isoformat(),
        "window_end": datetime.now(UTC).isoformat(),
        "jobs": {
            "erp_sync_runs": {
                "status_counts": _status_counts(erp_rows),
                "retryable_count": retryable_erp_runs,
                "safe_retry_statuses": sorted(_RETRYABLE_ERP_SYNC_STATUSES),
            },
            "fx_revaluation_runs": {
                "status_counts": _status_counts(revaluation_rows),
            },
            "fx_translation_runs": {
                "status_counts": _status_counts(translation_rows),
            },
            "audit_export_runs": {
                "status_counts": _status_counts(audit_export_rows),
            },
        },
    }


async def _session_visibility_payload(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    now_utc = datetime.now(UTC)
    active_count = int(
        (
            await session.execute(
                select(func.count(IamSession.id)).where(
                    IamSession.tenant_id == tenant_id,
                    IamSession.revoked_at.is_(None),
                    IamSession.expires_at > now_utc,
                )
            )
        ).scalar_one()
        or 0
    )
    revoked_count = int(
        (
            await session.execute(
                select(func.count(IamSession.id)).where(
                    IamSession.tenant_id == tenant_id,
                    IamSession.revoked_at.is_not(None),
                )
            )
        ).scalar_one()
        or 0
    )
    expired_count = int(
        (
            await session.execute(
                select(func.count(IamSession.id)).where(
                    IamSession.tenant_id == tenant_id,
                    IamSession.revoked_at.is_(None),
                    IamSession.expires_at <= now_utc,
                )
            )
        ).scalar_one()
        or 0
    )
    recent = (
        await session.execute(
            select(
                IamSession.user_id,
                IamSession.expires_at,
                IamSession.revoked_at,
                IamSession.created_at,
            )
            .where(IamSession.tenant_id == tenant_id)
            .order_by(IamSession.created_at.desc(), IamSession.id.desc())
            .limit(25)
        )
    ).all()

    return {
        "tenant_id": str(tenant_id),
        "active_sessions": active_count,
        "revoked_sessions": revoked_count,
        "expired_sessions": expired_count,
        "recent_sessions": [
            {
                "user_id": str(row.user_id),
                "status": (
                    "REVOKED"
                    if row.revoked_at is not None
                    else "EXPIRED"
                    if row.expires_at <= now_utc
                    else "ACTIVE"
                ),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            }
            for row in recent
        ],
    }


@router.get("/migrations/status")
async def get_migration_status(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    payload = await _migration_status_payload(session)
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/dependencies")
async def get_dependency_status(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    db_check, redis_check, workers_check, queues_check, temporal_check, ai_check = await asyncio.gather(
        health_api._check_database(),
        health_api._check_redis(),
        health_api._check_workers(),
        health_api._check_queues(),
        health_api._check_temporal(),
        health_api._check_ai(),
    )
    migration_check = await _migration_status_payload(session)
    payload = {
        "database": db_check,
        "redis": redis_check,
        "workers": workers_check,
        "queues": queues_check,
        "temporal": temporal_check,
        "ai": ai_check,
        "migrations": migration_check,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/jobs/status")
async def get_job_status(
    request: Request,
    lookback_hours: int = Query(default=24, ge=1, le=24 * 14),
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    target_tenant = tenant_id or user.tenant_id
    payload = await _ops_job_status_payload(
        session,
        tenant_id=target_tenant,
        lookback_hours=lookback_hours,
    )
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/jobs/erp-sync/{run_id}/retry")
async def retry_erp_sync_run(
    run_id: uuid.UUID,
    request: Request,
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    target_tenant = tenant_id or user.tenant_id
    run = (
        await session.execute(
            select(ExternalSyncRun).where(
                ExternalSyncRun.id == run_id,
                ExternalSyncRun.tenant_id == target_tenant,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="sync run not found")

    if run.run_status not in _RETRYABLE_ERP_SYNC_STATUSES or not run.is_resumable:
        raise HTTPException(
            status_code=409,
            detail=(
                "safe retry is supported only for resumable PAUSED runs. "
                "Use /api/v1/erp-sync/sync-runs to create a fresh run for FAILED/HALTED runs."
            ),
        )

    service = SyncService(session)
    idempotency_key = f"ops-retry:{run_id}:{datetime.now(UTC).isoformat()}"
    result = await service.resume_sync_run(
        tenant_id=target_tenant,
        paused_run_id=run.id,
        idempotency_key=idempotency_key,
        created_by=user.id,
    )
    await session.commit()
    payload = {
        "status": "accepted",
        "retry_mode": "resume",
        "source_run_id": str(run.id),
        "result": result,
    }
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sessions/status")
async def get_session_status(
    request: Request,
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    target_tenant = tenant_id or user.tenant_id
    payload = await _session_visibility_payload(session, tenant_id=target_tenant)
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/summary")
async def get_ops_summary(
    request: Request,
    lookback_hours: int = Query(default=24, ge=1, le=24 * 14),
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    target_tenant = tenant_id or user.tenant_id
    migration_payload, job_payload, session_payload = await asyncio.gather(
        _migration_status_payload(session),
        _ops_job_status_payload(
            session,
            tenant_id=target_tenant,
            lookback_hours=lookback_hours,
        ),
        _session_visibility_payload(
            session,
            tenant_id=target_tenant,
        ),
    )
    payload = {
        "migrations": migration_payload,
        "jobs": job_payload,
        "sessions": session_payload,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
