from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.core.governance.airlock import (
    AirlockActor,
    AirlockAdmissionService,
)
from financeops.db.models.governance_control import AirlockItem
from financeops.db.models.intent_pipeline import (
    CanonicalIntent,
    CanonicalIntentEvent,
    CanonicalJob,
)
from financeops.db.models.users import IamUser
from financeops.shared_kernel.response import ok

router = APIRouter()


def _serialize_intent(intent: CanonicalIntent) -> dict[str, Any]:
    return {
        "intent_id": str(intent.id),
        "intent_type": intent.intent_type,
        "status": intent.status,
        "module_key": intent.module_key,
        "target_type": intent.target_type,
        "target_id": str(intent.target_id) if intent.target_id else None,
        "org_id": str(intent.org_id),
        "entity_id": str(intent.entity_id),
        "requested_by_user_id": str(intent.requested_by_user_id),
        "requested_by_role": intent.requested_by_role,
        "requested_at": intent.requested_at.isoformat() if intent.requested_at else None,
        "submitted_at": intent.submitted_at.isoformat() if intent.submitted_at else None,
        "validated_at": intent.validated_at.isoformat() if intent.validated_at else None,
        "approved_at": intent.approved_at.isoformat() if intent.approved_at else None,
        "executed_at": intent.executed_at.isoformat() if intent.executed_at else None,
        "recorded_at": intent.recorded_at.isoformat() if intent.recorded_at else None,
        "rejected_at": intent.rejected_at.isoformat() if intent.rejected_at else None,
        "rejection_reason": intent.rejection_reason,
        "source_channel": intent.source_channel,
        "job_id": str(intent.job_id) if intent.job_id else None,
        "record_refs": intent.record_refs_json,
        "guard_results": intent.guard_results_json,
        "payload": intent.payload_json,
        "next_action": None,
    }


def _serialize_job(job: CanonicalJob, *, entity_id: uuid.UUID | None, intent_id: uuid.UUID) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "intent_id": str(intent_id),
        "entity_id": str(entity_id) if entity_id else None,
        "job_type": job.job_type,
        "status": job.status,
        "runner_type": job.runner_type,
        "queue_name": job.queue_name,
        "requested_at": job.requested_at.isoformat() if job.requested_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "error_details": job.error_details_json,
    }


def _serialize_airlock_item(item: AirlockItem) -> dict[str, Any]:
    return {
        "airlock_item_id": str(item.id),
        "entity_id": str(item.entity_id) if item.entity_id else None,
        "source_type": item.source_type,
        "source_reference": item.source_reference,
        "file_name": item.file_name,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "checksum_sha256": item.checksum_sha256,
        "status": item.status,
        "submitted_by_user_id": str(item.submitted_by_user_id),
        "reviewed_by_user_id": str(item.reviewed_by_user_id) if item.reviewed_by_user_id else None,
        "admitted_by_user_id": str(item.admitted_by_user_id) if item.admitted_by_user_id else None,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "admitted_at": item.admitted_at.isoformat() if item.admitted_at else None,
        "rejected_at": item.rejected_at.isoformat() if item.rejected_at else None,
        "rejection_reason": item.rejection_reason,
        "metadata": item.metadata_json,
        "findings": item.findings_json,
    }


@router.get("/intents")
async def list_intents_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    stmt = select(CanonicalIntent).where(CanonicalIntent.tenant_id == user.tenant_id)
    if entity_id is not None:
        stmt = stmt.where(CanonicalIntent.entity_id == entity_id)
    if status:
        stmt = stmt.where(CanonicalIntent.status == status)
    stmt = stmt.order_by(CanonicalIntent.requested_at.desc(), CanonicalIntent.id.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ok(
        [_serialize_intent(row) for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/intents/{intent_id}")
async def get_intent_endpoint(
    intent_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    intent = (
        await session.execute(
            select(CanonicalIntent).where(
                CanonicalIntent.tenant_id == user.tenant_id,
                CanonicalIntent.id == intent_id,
            )
        )
    ).scalar_one()
    events = (
        await session.execute(
            select(CanonicalIntentEvent)
            .where(CanonicalIntentEvent.tenant_id == user.tenant_id, CanonicalIntentEvent.intent_id == intent.id)
            .order_by(CanonicalIntentEvent.event_at.asc(), CanonicalIntentEvent.id.asc())
        )
    ).scalars().all()
    payload = _serialize_intent(intent)
    payload["events"] = [
        {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
            "actor_role": event.actor_role,
            "event_at": event.event_at.isoformat() if event.event_at else None,
            "payload": event.event_payload_json,
        }
        for event in events
    ]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/jobs")
async def list_jobs_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    stmt = (
        select(CanonicalJob, CanonicalIntent.id, CanonicalIntent.entity_id)
        .join(CanonicalIntent, CanonicalIntent.id == CanonicalJob.intent_id)
        .where(CanonicalIntent.tenant_id == user.tenant_id)
    )
    if entity_id is not None:
        stmt = stmt.where(CanonicalIntent.entity_id == entity_id)
    if status:
        stmt = stmt.where(CanonicalJob.status == status)
    stmt = stmt.order_by(CanonicalJob.requested_at.desc(), CanonicalJob.id.desc()).limit(limit)
    rows = (await session.execute(stmt)).all()
    return ok(
        [
            _serialize_job(job, entity_id=row_entity_id, intent_id=row_intent_id)
            for job, row_intent_id, row_entity_id in rows
        ],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/airlock")
async def list_airlock_items_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    stmt = select(AirlockItem).where(AirlockItem.tenant_id == user.tenant_id)
    if entity_id is not None:
        stmt = stmt.where(AirlockItem.entity_id == entity_id)
    if status:
        stmt = stmt.where(AirlockItem.status == status)
    stmt = stmt.order_by(AirlockItem.submitted_at.desc(), AirlockItem.id.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ok(
        [_serialize_airlock_item(item) for item in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/airlock/{item_id}")
async def get_airlock_item_endpoint(
    item_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    item = await AirlockAdmissionService().get_item(
        session,
        tenant_id=user.tenant_id,
        item_id=item_id,
    )
    return ok(
        _serialize_airlock_item(item),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/airlock/{item_id}/admit")
async def admit_airlock_item_endpoint(
    item_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    result = await AirlockAdmissionService().admit_airlock_item(
        session,
        item_id=item_id,
        actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
    )
    await session.flush()
    return ok(
        {
            "airlock_item_id": str(result.item_id),
            "status": result.status,
            "admitted": result.admitted,
            "checksum_sha256": result.checksum_sha256,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/airlock/{item_id}/reject")
async def reject_airlock_item_endpoint(
    item_id: uuid.UUID,
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    reason = str(body.get("reason") or "").strip() or "Rejected from control plane review."
    result = await AirlockAdmissionService().reject_airlock_item(
        session,
        item_id=item_id,
        actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
        reason=reason,
    )
    await session.flush()
    return ok(
        {
            "airlock_item_id": str(result.item_id),
            "status": result.status,
            "admitted": result.admitted,
            "checksum_sha256": result.checksum_sha256,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
