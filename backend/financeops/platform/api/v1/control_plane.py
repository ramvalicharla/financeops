from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.core.governance.airlock import (
    AirlockActor,
    AirlockAdmissionService,
)
from financeops.db.models.accounting_governance import AccountingPeriod
from financeops.db.models.governance_control import AirlockItem
from financeops.db.models.intent_pipeline import (
    CanonicalIntent,
    CanonicalIntentEvent,
    CanonicalJob,
)
from financeops.db.models.users import IamUser
from financeops.modules.org_setup.models import OrgGroup
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenant_module_enablement import CpTenantModuleEnablement
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService
from financeops.platform.services.tenancy.entity_access import get_entities_for_user
from financeops.shared_kernel.response import ok

router = APIRouter()

_WORKSPACE_LABELS: dict[str, str] = {
    "dashboard": "Dashboard",
    "erp": "ERP",
    "accounting": "Accounting",
    "reconciliation": "Reconciliation",
    "close": "Close",
    "reports": "Reports",
    "settings": "Settings",
}


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
    retry_supported = False
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
        "capabilities": {
            "retry": {
                "supported": retry_supported,
                "allowed": retry_supported and job.status in {"FAILED", "ERROR"},
                "reason": (
                    "Not supported in current backend contract"
                    if not retry_supported
                    else None
                ),
            }
        },
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


def _phase4_service(session: AsyncSession) -> Phase4ControlPlaneService:
    return Phase4ControlPlaneService(session)


async def _enabled_modules(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    as_of = datetime.now(UTC)
    rows = (
        await session.execute(
            select(CpModuleRegistry, CpTenantModuleEnablement)
            .join(
                CpTenantModuleEnablement,
                CpTenantModuleEnablement.module_id == CpModuleRegistry.id,
            )
            .where(
                CpTenantModuleEnablement.tenant_id == tenant_id,
                CpTenantModuleEnablement.enabled.is_(True),
                CpTenantModuleEnablement.effective_from <= as_of,
                (
                    CpTenantModuleEnablement.effective_to.is_(None)
                    | (CpTenantModuleEnablement.effective_to > as_of)
                ),
                CpModuleRegistry.is_active.is_(True),
            )
            .order_by(CpModuleRegistry.module_code.asc(), CpTenantModuleEnablement.effective_from.desc())
        )
    ).all()
    enabled: dict[str, dict[str, Any]] = {}
    for module_row, enablement_row in rows:
        enabled.setdefault(
            module_row.module_code,
            {
                "module_id": str(module_row.id),
                "module_code": module_row.module_code,
                "module_name": module_row.module_name,
                "engine_context": module_row.engine_context,
                "is_financial_impacting": bool(module_row.is_financial_impacting),
                "effective_from": enablement_row.effective_from.isoformat(),
            },
        )
    return list(enabled.values())


async def _current_period(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(UTC)
    period = (
        await session.execute(
            select(AccountingPeriod)
            .where(
                AccountingPeriod.tenant_id == tenant_id,
                AccountingPeriod.fiscal_year == now.year,
                AccountingPeriod.period_number == now.month,
                AccountingPeriod.org_entity_id.is_(None),
            )
            .order_by(AccountingPeriod.created_at.desc())
        )
    ).scalar_one_or_none()
    if period is None:
        return {
            "period_label": f"{now.year:04d}-{now.month:02d}",
            "fiscal_year": now.year,
            "period_number": now.month,
            "source": "server_clock",
            "period_id": None,
            "status": None,
        }
    return {
        "period_label": f"{period.fiscal_year:04d}-{period.period_number:02d}",
        "fiscal_year": period.fiscal_year,
        "period_number": period.period_number,
        "source": "accounting_period",
        "period_id": str(period.id),
        "status": period.status,
    }


async def _current_organisation(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict[str, Any]:
    group = (
        await session.execute(
            select(OrgGroup)
            .where(OrgGroup.tenant_id == tenant_id)
            .order_by(OrgGroup.created_at.asc(), OrgGroup.id.asc())
        )
    ).scalars().first()
    if group is None:
        return {
            "organisation_id": None,
            "organisation_name": None,
            "source": "unavailable",
        }
    return {
        "organisation_id": str(group.id),
        "organisation_name": group.group_name,
        "source": "org_group",
    }


async def _current_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: str,
    requested_entity_id: uuid.UUID | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    entities = await get_entities_for_user(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
    )
    available_entities = [
        {
            "entity_id": str(entity.id),
            "entity_code": entity.entity_code,
            "entity_name": entity.entity_name,
        }
        for entity in entities
    ]
    if not entities:
        return (
            {
                "entity_id": None,
                "entity_code": None,
                "entity_name": None,
                "source": "unavailable",
            },
            available_entities,
        )

    selected = None
    source = "default_access_scope"
    if requested_entity_id is not None:
        for entity in entities:
            if entity.id == requested_entity_id:
                selected = entity
                source = "requested_entity"
                break
    if selected is None:
        selected = entities[0]
    return (
        {
            "entity_id": str(selected.id),
            "entity_code": selected.entity_code,
            "entity_name": selected.entity_name,
            "source": source,
        },
        available_entities,
    )


def _current_workspace(
    *,
    enabled_modules: list[dict[str, Any]],
    requested_workspace: str | None,
    requested_module: str | None,
) -> dict[str, Any]:
    candidate = (requested_module or requested_workspace or "").strip()
    if candidate and candidate in _WORKSPACE_LABELS:
        return {
            "module_key": candidate,
            "module_name": _WORKSPACE_LABELS[candidate],
            "module_code": None,
            "source": "requested_workspace",
        }
    if candidate:
        for enabled in enabled_modules:
            if candidate in {str(enabled["module_code"]), str(enabled["module_name"])}:
                return {
                    "module_key": str(enabled["module_code"]),
                    "module_name": str(enabled["module_name"]),
                    "module_code": str(enabled["module_code"]),
                    "source": "requested_module",
                }
    if enabled_modules:
        first = enabled_modules[0]
        return {
            "module_key": str(first["module_code"]),
            "module_name": str(first["module_name"]),
            "module_code": str(first["module_code"]),
            "source": "enabled_module_default",
        }
    return {
        "module_key": None,
        "module_name": None,
        "module_code": None,
        "source": "unavailable",
    }


def _timeline_semantics_payload() -> dict[str, Any]:
    return {
        "title": "Timeline",
        "description": "Control-plane events returned by the backend timeline API.",
        "empty_state": "No control-plane events in the current scope.",
        "semantics": {
            "authoritative": True,
            "append_only_guarantee": False,
            "compliance_grade": False,
            "label_mode": "control_plane_events",
        },
    }


@router.get("/context")
async def get_control_plane_context_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    workspace: str | None = Query(default=None),
    module: str | None = Query(default=None),
) -> dict[str, Any]:
    enabled_modules = await _enabled_modules(session, tenant_id=user.tenant_id)
    current_entity, available_entities = await _current_entity(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role.value,
        requested_entity_id=entity_id,
    )
    payload = {
        "tenant_id": str(user.tenant_id),
        "tenant_slug": getattr(user, "tenant_slug", None),
        "enabled_modules": enabled_modules,
        "current_organisation": await _current_organisation(session, tenant_id=user.tenant_id),
        "current_entity": current_entity,
        "available_entities": available_entities,
        "current_module": _current_workspace(
            enabled_modules=enabled_modules,
            requested_workspace=workspace,
            requested_module=module,
        ),
        "current_period": await _current_period(session, tenant_id=user.tenant_id),
    }
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


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


@router.get("/timeline")
async def list_timeline_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    payload = await _phase4_service(session).build_timeline(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        subject_type=subject_type,
        subject_id=subject_id,
        limit=limit,
    )
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/timeline/semantics")
async def get_timeline_semantics_endpoint(
    request: Request,
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    payload = {
        **_timeline_semantics_payload(),
        "viewer_role": user.role.value,
    }
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/timeline/export")
async def export_timeline_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
) -> Response:
    payload = await _phase4_service(session).build_timeline(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        subject_type=subject_type,
        subject_id=subject_id,
        limit=limit,
    )
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=timeline-export.json"},
    )


@router.get("/determinism")
async def get_determinism_endpoint(
    request: Request,
    subject_type: str = Query(...),
    subject_id: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    try:
        payload = await _phase4_service(session).build_determinism_summary(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/determinism/verify")
async def verify_determinism_endpoint(
    request: Request,
    subject_type: str = Query(...),
    subject_id: str = Query(...),
    expected_hash: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    try:
        payload = await _phase4_service(session).verify_determinism_hash(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            subject_type=subject_type,
            subject_id=subject_id,
            expected_hash=expected_hash,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/lineage")
async def get_lineage_endpoint(
    request: Request,
    subject_type: str = Query(...),
    subject_id: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    try:
        payload = await _phase4_service(session).build_lineage(
            tenant_id=user.tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/impact")
async def get_impact_endpoint(
    request: Request,
    subject_type: str = Query(...),
    subject_id: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    try:
        payload = await _phase4_service(session).build_impact(
            tenant_id=user.tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/snapshots")
async def list_snapshots_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    entity_id: uuid.UUID | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    payload = await _phase4_service(session).list_snapshots(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        subject_type=subject_type,
        limit=limit,
    )
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/snapshots/manual")
async def create_manual_snapshot_endpoint(
    body: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict[str, Any]:
    subject_type = str(body.get("subject_type") or "").strip()
    subject_id = str(body.get("subject_id") or "").strip()
    if not subject_type or not subject_id:
        raise HTTPException(status_code=422, detail="subject_type and subject_id are required")
    payload = await _phase4_service(session).create_manual_snapshot(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        actor_role=user.role.value,
        subject_type=subject_type,
        subject_id=subject_id,
        trigger_event="manual_snapshot",
    )
    await session.flush()
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    payload = await _phase4_service(session).get_snapshot(
        tenant_id=user.tenant_id,
        snapshot_id=snapshot_id,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/snapshots/{snapshot_id}/compare/{other_snapshot_id}")
async def compare_snapshots_endpoint(
    snapshot_id: uuid.UUID,
    other_snapshot_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    try:
        payload = await _phase4_service(session).compare_snapshots(
            tenant_id=user.tenant_id,
            left_snapshot_id=snapshot_id,
            right_snapshot_id=other_snapshot_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/audit-pack")
async def get_audit_pack_endpoint(
    subject_type: str = Query(...),
    subject_id: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> Response:
    try:
        payload = await _phase4_service(session).build_audit_pack(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit-pack.json"},
    )
