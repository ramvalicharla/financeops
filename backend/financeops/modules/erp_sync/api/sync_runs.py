from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import (
    ExternalSyncDriftReport,
    ExternalSyncError,
    ExternalSyncEvidenceLink,
    ExternalSyncRun,
)
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.publish_service import PublishService
from financeops.modules.erp_sync.application.sync_service import SyncService
from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.auto_trigger.pipeline import trigger_post_sync_pipeline
from financeops.security.antivirus import AntivirusUnavailableError, scan_file
from financeops.security.file_validation import FileValidationError, validate_file
from financeops.shared_kernel.idempotency import optional_idempotency_key, require_erp_sync_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/sync-runs")
async def create_sync_run(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    idempotency_key: str = Depends(require_erp_sync_idempotency_key),
) -> dict[str, Any]:
    content_bytes = b""
    filename = str(body.get("file_name", "data.csv"))
    if body.get("file_content_base64"):
        content_bytes = base64.b64decode(str(body["file_content_base64"]))
        try:
            validate_file(filename=filename, content=content_bytes)
            scan_result = await scan_file(content=content_bytes, filename=filename)
        except FileValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_validation_failed:{exc.reason}",
            ) from exc
        except AntivirusUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="antivirus_unavailable",
            ) from exc
        if not scan_result.clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"malware_detected:{scan_result.threat_name or 'unknown'}",
            )

    sync_service = SyncService(session)
    result = await sync_service.trigger_sync_run(
        tenant_id=user.tenant_id,
        organisation_id=uuid.UUID(str(body.get("organisation_id", user.tenant_id))),
        entity_id=uuid.UUID(str(body["entity_id"])) if body.get("entity_id") else None,
        connection_id=uuid.UUID(str(body["connection_id"])),
        sync_definition_id=uuid.UUID(str(body["sync_definition_id"])),
        sync_definition_version_id=uuid.UUID(str(body["sync_definition_version_id"])),
        dataset_type=DatasetType(str(body["dataset_type"])),
        idempotency_key=idempotency_key,
        created_by=user.id,
        extraction_kwargs={
            "content": content_bytes,
            "filename": filename,
            "checkpoint": body.get("checkpoint"),
        },
    )
    await session.flush()
    if str(result.get("sync_run_status", "")).lower() == "completed":
        try:
            trigger_post_sync_pipeline.delay(
                tenant_id=str(user.tenant_id),
                sync_run_id=str(result["sync_run_id"]),
            )
        except Exception as exc:
            log.warning(
                "Auto-trigger enqueue failed for sync_run_id=%s tenant_id=%s: %s",
                result.get("sync_run_id"),
                user.tenant_id,
                exc,
            )
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sync-runs")
async def list_sync_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(ExternalSyncRun).where(ExternalSyncRun.tenant_id == user.tenant_id).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ExternalSyncRun)
            .where(ExternalSyncRun.tenant_id == user.tenant_id)
            .order_by(ExternalSyncRun.created_at.desc(), ExternalSyncRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        {
            "id": str(row.id),
            "dataset_type": row.dataset_type,
            "run_status": row.run_status,
            "run_token": row.run_token,
            "reporting_period_label": row.reporting_period_label,
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {"data": items, "total": int(total), "limit": limit, "offset": offset}
    else:
        payload = {"items": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sync-runs/{id}")
async def get_sync_run(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalSyncRun).where(
                ExternalSyncRun.tenant_id == user.tenant_id,
                ExternalSyncRun.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "dataset_type": row.dataset_type,
            "run_status": row.run_status,
            "run_token": row.run_token,
            "validation_summary_json": row.validation_summary_json,
            "extraction_checkpoint": row.extraction_checkpoint,
            "is_resumable": row.is_resumable,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/sync-runs/{id}/evidence")
async def get_sync_run_evidence(
    request: Request,
    id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(ExternalSyncEvidenceLink).where(
                    ExternalSyncEvidenceLink.tenant_id == user.tenant_id,
                    ExternalSyncEvidenceLink.sync_run_id == uuid.UUID(id),
                ).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ExternalSyncEvidenceLink).where(
                ExternalSyncEvidenceLink.tenant_id == user.tenant_id,
                ExternalSyncEvidenceLink.sync_run_id == uuid.UUID(id),
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        {
            "id": str(row.id),
            "evidence_type": row.evidence_type,
            "evidence_ref": row.evidence_ref,
            "evidence_label": row.evidence_label,
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {
            "id": id,
            "data": items,
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }
    else:
        payload = {"id": id, "evidence": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sync-runs/{id}/errors")
async def get_sync_run_errors(
    request: Request,
    id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(ExternalSyncError).where(
                    ExternalSyncError.tenant_id == user.tenant_id,
                    ExternalSyncError.sync_run_id == uuid.UUID(id),
                ).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ExternalSyncError).where(
                ExternalSyncError.tenant_id == user.tenant_id,
                ExternalSyncError.sync_run_id == uuid.UUID(id),
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        {
            "id": str(row.id),
            "error_code": row.error_code,
            "severity": row.severity,
            "message": row.message,
            "details_json": row.details_json,
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {
            "id": id,
            "data": items,
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }
    else:
        payload = {"id": id, "errors": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sync-runs/{id}/drift-report")
async def get_sync_run_drift_report(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalSyncDriftReport).where(
                ExternalSyncDriftReport.tenant_id == user.tenant_id,
                ExternalSyncDriftReport.sync_run_id == uuid.UUID(id),
            )
        )
    ).scalar_one_or_none()
    return ok(
        {
            "id": id,
            "drift": None
            if row is None
            else {
                "drift_report_id": str(row.id),
                "drift_detected": row.drift_detected,
                "drift_severity": row.drift_severity,
                "total_variances": row.total_variances,
            },
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync-runs/{id}/replay")
async def replay_sync_run(request: Request, id: str) -> dict[str, Any]:
    return ok(
        {"id": id, "status": "accepted", "note": "replay endpoint queued"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync-runs/{id}/resume")
async def resume_sync_run(
    request: Request,
    id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    sync_service = SyncService(session)
    result = await sync_service.resume_sync_run(
        tenant_id=user.tenant_id,
        paused_run_id=uuid.UUID(id),
        idempotency_key=str(body.get("idempotency_key", f"resume:{id}")),
        created_by=user.id,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync-runs/{id}/publish")
async def publish_sync_run(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    idempotency_key: str | None = Depends(optional_idempotency_key),
) -> dict[str, Any]:
    publish_service = PublishService(session)
    result = await publish_service.approve_publish_event(
        tenant_id=user.tenant_id,
        sync_run_id=uuid.UUID(id),
        idempotency_key=idempotency_key or f"sync-run-publish:{id}",
        actor_user_id=user.id,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
