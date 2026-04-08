from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.config import limiter, settings
from financeops.core.governance.airlock import AirlockActor, AirlockAdmissionService
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
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
from financeops.modules.closing_checklist.service import run_auto_complete_for_event
from financeops.modules.auto_trigger.pipeline import trigger_post_sync_pipeline
from financeops.shared_kernel.idempotency import optional_idempotency_key, require_erp_sync_idempotency_key
from financeops.shared_kernel.response import ok
from financeops.observability.workflow_signals import (
    complete_workflow,
    fail_workflow,
    observe_erp_sync,
    start_workflow,
)

router = APIRouter()
log = logging.getLogger(__name__)


@limiter.limit(settings.ERP_SYNC_WRITE_RATE_LIMIT)
@router.post("/sync-runs")
async def create_sync_run(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    idempotency_key: str = Depends(require_erp_sync_idempotency_key),
) -> dict[str, Any]:
    started = time.perf_counter()
    workflow_timer = start_workflow(
        workflow="erp_sync_run",
        tenant_id=str(user.tenant_id),
        module="erp_sync",
        correlation_id=str(getattr(request.state, "correlation_id", "") or "") or None,
    )
    content_bytes = b""
    filename = str(body.get("file_name", "data.csv"))
    try:
        if body.get("file_content_base64"):
            content_bytes = base64.b64decode(str(body["file_content_base64"]))
        airlock_service = AirlockAdmissionService()
        airlock_result = await airlock_service.submit_external_input(
            session,
            source_type="erp_sync_upload" if content_bytes else "erp_sync_request",
            actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
            metadata={
                "connection_id": str(body["connection_id"]),
                "sync_definition_id": str(body["sync_definition_id"]),
                "sync_definition_version_id": str(body["sync_definition_version_id"]),
                "dataset_type": str(body["dataset_type"]),
            },
            content=content_bytes or None,
            file_name=filename if content_bytes else None,
            entity_id=uuid.UUID(str(body["entity_id"])) if body.get("entity_id") else None,
            source_reference=str(body.get("connection_id") or ""),
            idempotency_key=idempotency_key,
        )
        airlock_result = await airlock_service.admit_airlock_item(
            session,
            item_id=airlock_result.item_id,
            actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
        )

        result = await IntentService(session).submit_intent(
            intent_type=IntentType.CREATE_ERP_SYNC_RUN,
            actor=IntentActor(
                user_id=user.id,
                tenant_id=user.tenant_id,
                role=user.role.value,
                source_channel=IntentSourceChannel.API.value,
                request_id=str(getattr(request.state, "request_id", "") or "") or None,
                correlation_id=str(getattr(request.state, "correlation_id", "") or "") or None,
            ),
            payload={
                "organisation_id": str(body.get("organisation_id", user.tenant_id)),
                "entity_id": str(body["entity_id"]) if body.get("entity_id") else None,
                "connection_id": str(body["connection_id"]),
                "sync_definition_id": str(body["sync_definition_id"]),
                "sync_definition_version_id": str(body["sync_definition_version_id"]),
                "dataset_type": str(body["dataset_type"]),
                "checkpoint": body.get("checkpoint"),
                "file_name": filename,
                "file_content_base64": str(body.get("file_content_base64") or ""),
                "admitted_airlock_item_id": str(airlock_result.item_id),
                "source_type": "erp_sync_upload" if content_bytes else "erp_sync_request",
                "source_external_ref": str(body.get("connection_id") or ""),
            },
            idempotency_key=idempotency_key,
        )
        await session.flush()
        if str((result.record_refs or {}).get("sync_run_status", "")).lower() == "completed":
            try:
                trigger_post_sync_pipeline.delay(
                    tenant_id=str(user.tenant_id),
                    sync_run_id=str((result.record_refs or {})["sync_run_id"]),
                )
            except Exception as exc:
                log.warning(
                    "Auto-trigger enqueue failed for sync_run_id=%s tenant_id=%s: %s",
                    (result.record_refs or {}).get("sync_run_id"),
                    user.tenant_id,
                    exc,
                )
            period = str(body.get("period") or body.get("reporting_period_label") or datetime.now(UTC).strftime("%Y-%m"))
            asyncio.create_task(
                run_auto_complete_for_event(
                    tenant_id=user.tenant_id,
                    period=period,
                    event="erp_sync_complete",
                )
            )
        duration_ms = (time.perf_counter() - started) * 1000
        observe_erp_sync(
            operation="sync_run_create",
            status="success",
            connector_type=str(body.get("dataset_type", "unknown")),
            duration_ms=duration_ms,
        )
        complete_workflow(
            workflow_timer,
            status="success",
            extra={"run_id": str((result.record_refs or {}).get("sync_run_id") or "")},
        )
        response_payload = {
            "intent_id": str(result.intent_id),
            "status": result.status,
            "job_id": str(result.job_id) if result.job_id else None,
            "next_action": result.next_action,
            "record_refs": result.record_refs or {},
            "airlock_item_id": str(airlock_result.item_id),
        }
        return ok(response_payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        observe_erp_sync(
            operation="sync_run_create",
            status="failed",
            connector_type=str(body.get("dataset_type", "unknown")),
            duration_ms=duration_ms,
        )
        fail_workflow(workflow_timer, error=exc)
        raise


@router.get("/sync-runs")
async def list_sync_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    filters = [ExternalSyncRun.tenant_id == user.tenant_id]
    if connection_id:
        filters.append(ExternalSyncRun.connection_id == uuid.UUID(connection_id))
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = int(
        (
            await session.execute(
                select(func.count(ExternalSyncRun.id)).where(
                    *filters
                )
            )
        ).scalar_one()
        or 0
    )
    rows = (await session.execute(
            select(
                ExternalSyncRun.id,
                ExternalSyncRun.connection_id,
                ExternalSyncRun.dataset_type,
                ExternalSyncRun.run_status,
                ExternalSyncRun.run_token,
                ExternalSyncRun.reporting_period_label,
                ExternalSyncRun.created_at,
                ExternalSyncRun.published_at,
                ExternalSyncRun.extraction_fetched_records,
                ExternalSyncRun.validation_summary_json,
            )
            .where(*filters)
            .order_by(ExternalSyncRun.created_at.desc(), ExternalSyncRun.id.desc())
            .limit(limit)
            .offset(offset)
        )).all()
    items = [
        {
            "id": str(row.id),
            "connection_id": str(row.connection_id),
            "dataset_type": row.dataset_type,
            "run_status": row.run_status,
            "run_token": row.run_token,
            "reporting_period_label": row.reporting_period_label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "extraction_fetched_records": int(row.extraction_fetched_records or 0),
            "validation_summary_json": row.validation_summary_json or {},
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {"data": items, "total": total, "limit": limit, "offset": offset}
    else:
        payload = {"items": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/sync-runs/{id}")
async def get_sync_run(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
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
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = int(
        (
            await session.execute(
                select(func.count(ExternalSyncEvidenceLink.id)).where(
                    ExternalSyncEvidenceLink.tenant_id == user.tenant_id,
                    ExternalSyncEvidenceLink.sync_run_id == uuid.UUID(id),
                )
            )
        ).scalar_one()
        or 0
    )
    rows = (await session.execute(
            select(
                ExternalSyncEvidenceLink.id,
                ExternalSyncEvidenceLink.evidence_type,
                ExternalSyncEvidenceLink.evidence_ref,
                ExternalSyncEvidenceLink.evidence_label,
            ).where(
                ExternalSyncEvidenceLink.tenant_id == user.tenant_id,
                ExternalSyncEvidenceLink.sync_run_id == uuid.UUID(id),
            )
            .limit(limit)
            .offset(offset)
        )).all()
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
            "total": total,
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
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = int(
        (
            await session.execute(
                select(func.count(ExternalSyncError.id)).where(
                    ExternalSyncError.tenant_id == user.tenant_id,
                    ExternalSyncError.sync_run_id == uuid.UUID(id),
                )
            )
        ).scalar_one()
        or 0
    )
    rows = (await session.execute(
            select(
                ExternalSyncError.id,
                ExternalSyncError.error_code,
                ExternalSyncError.severity,
                ExternalSyncError.message,
                ExternalSyncError.details_json,
            ).where(
                ExternalSyncError.tenant_id == user.tenant_id,
                ExternalSyncError.sync_run_id == uuid.UUID(id),
            )
            .limit(limit)
            .offset(offset)
        )).all()
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
            "total": total,
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
    user: IamUser = Depends(require_finance_team),
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


@limiter.limit(settings.ERP_SYNC_WRITE_RATE_LIMIT)
@router.post("/sync-runs/{id}/replay")
async def replay_sync_run(
    request: Request,
    id: str,
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    _ = user
    observe_erp_sync(
        operation="sync_run_replay",
        status="success",
        connector_type="unknown",
    )
    return ok(
        {"id": id, "status": "accepted", "note": "replay endpoint queued"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@limiter.limit(settings.ERP_SYNC_WRITE_RATE_LIMIT)
@router.post("/sync-runs/{id}/resume")
async def resume_sync_run(
    request: Request,
    id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    started = time.perf_counter()
    sync_service = SyncService(session)
    try:
        result = await sync_service.resume_sync_run(
            tenant_id=user.tenant_id,
            paused_run_id=uuid.UUID(id),
            idempotency_key=str(body.get("idempotency_key", f"resume:{id}")),
            created_by=user.id,
        )
        await session.flush()
        observe_erp_sync(
            operation="sync_run_resume",
            status="success",
            connector_type="unknown",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
    except Exception:
        observe_erp_sync(
            operation="sync_run_resume",
            status="failed",
            connector_type="unknown",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise


@limiter.limit(settings.ERP_SYNC_WRITE_RATE_LIMIT)
@router.post("/sync-runs/{id}/publish")
async def publish_sync_run(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    idempotency_key: str | None = Depends(optional_idempotency_key),
) -> dict[str, Any]:
    started = time.perf_counter()
    publish_service = PublishService(session)
    try:
        result = await publish_service.approve_publish_event(
            tenant_id=user.tenant_id,
            sync_run_id=uuid.UUID(id),
            idempotency_key=idempotency_key or f"sync-run-publish:{id}",
            actor_user_id=user.id,
        )
        await session.flush()
        observe_erp_sync(
            operation="sync_run_publish",
            status="success",
            connector_type="unknown",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
    except Exception:
        observe_erp_sync(
            operation="sync_run_publish",
            status="failed",
            connector_type="unknown",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise

