from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.config import limiter
from financeops.db.models.users import IamUser
from financeops.modules.auditor_portal.deps import get_auditor_access
from financeops.modules.auditor_portal.models import AuditorPortalAccess, AuditorRequest
from financeops.modules.auditor_portal.service import (
    create_auditor_request,
    get_pbc_tracker,
    grant_auditor_access,
    list_access,
    respond_to_request,
    revoke_access,
    seed_pbc_checklist,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/audit", tags=["audit_portal"])


class GrantAccessRequest(BaseModel):
    auditor_email: str
    auditor_firm: str
    engagement_name: str
    valid_from: date
    valid_until: date
    modules_accessible: list[str] = []
    access_level: str = "read_only"


class RespondRequest(BaseModel):
    status: str
    response_notes: str | None = None
    evidence_urls: list[str] = []


class AuditorCreateRequest(BaseModel):
    category: str
    description: str
    due_date: date | None = None


def _serialize_access(row: AuditorPortalAccess) -> dict:
    return {
        "id": str(row.id),
        "auditor_email": row.auditor_email,
        "auditor_firm": row.auditor_firm,
        "engagement_name": row.engagement_name,
        "access_level": row.access_level,
        "modules_accessible": row.modules_accessible or [],
        "valid_from": row.valid_from.isoformat(),
        "valid_until": row.valid_until.isoformat(),
        "is_active": row.is_active,
        "last_accessed_at": row.last_accessed_at.isoformat() if row.last_accessed_at else None,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_request(row: AuditorRequest) -> dict:
    return {
        "id": str(row.id),
        "access_id": str(row.access_id),
        "request_number": row.request_number,
        "category": row.category,
        "description": row.description,
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "response_notes": row.response_notes,
        "evidence_urls": row.evidence_urls or [],
        "provided_at": row.provided_at.isoformat() if row.provided_at else None,
        "provided_by": str(row.provided_by) if row.provided_by else None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/access/grant")
async def grant_access_endpoint(
    body: GrantAccessRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    access, plain_token = await grant_auditor_access(
        session,
        tenant_id=user.tenant_id,
        auditor_email=body.auditor_email,
        auditor_firm=body.auditor_firm,
        engagement_name=body.engagement_name,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        modules_accessible=body.modules_accessible,
        created_by=user.id,
        access_level=body.access_level,
    )
    await seed_pbc_checklist(session, access_id=access.id, tenant_id=user.tenant_id)
    return {"access": _serialize_access(access), "token": plain_token}


@router.get("/access", response_model=Paginated[dict])
async def list_access_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    payload = await list_access(session, tenant_id=user.tenant_id, limit=limit, offset=offset)
    return Paginated[dict](data=[_serialize_access(row) for row in payload["data"]], total=payload["total"], limit=payload["limit"], offset=payload["offset"])


@router.patch("/access/{access_id}/revoke")
async def revoke_access_endpoint(
    access_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await revoke_access(session, tenant_id=user.tenant_id, access_id=access_id)
    return _serialize_access(row)


@router.get("/{engagement_id}/pbc")
async def pbc_tracker_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    payload = await get_pbc_tracker(session, access_id=engagement_id, tenant_id=user.tenant_id)
    return {
        "engagement_name": payload["engagement_name"],
        "total_requests": payload["total_requests"],
        "open": payload["open"],
        "in_progress": payload["in_progress"],
        "provided": payload["provided"],
        "completion_pct": format(Decimal(str(payload["completion_pct"])), "f"),
        "overdue_requests": [_serialize_request(row) for row in payload["overdue_requests"]],
        "recent_activity": [_serialize_request(row) for row in payload["recent_activity"]],
    }


@router.post("/{engagement_id}/requests/{request_id}/respond")
async def respond_endpoint(
    engagement_id: uuid.UUID,
    request_id: uuid.UUID,
    body: RespondRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    del engagement_id
    row = await respond_to_request(
        session,
        tenant_id=user.tenant_id,
        request_id=request_id,
        status=body.status,
        response_notes=body.response_notes,
        evidence_urls=body.evidence_urls,
        provided_by=user.id,
    )
    return _serialize_request(row)


@limiter.limit("30/minute")
@router.get("/portal/requests")
async def auditor_list_requests_endpoint(
    request: Request,
    access: AuditorPortalAccess = Depends(get_auditor_access),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    del request
    rows = (
        await session.execute(
            select(AuditorRequest)
            .where(AuditorRequest.access_id == access.id, AuditorRequest.tenant_id == access.tenant_id)
            .order_by(AuditorRequest.request_number, AuditorRequest.created_at)
        )
    ).scalars().all()
    return {"requests": [_serialize_request(row) for row in rows]}


@limiter.limit("10/minute")
@router.post("/portal/requests")
async def auditor_create_request_endpoint(
    request: Request,
    body: AuditorCreateRequest,
    access: AuditorPortalAccess = Depends(get_auditor_access),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    del request
    row = await create_auditor_request(
        session,
        access=access,
        category=body.category,
        description=body.description,
        due_date=body.due_date,
    )
    return {"created": True, "request": _serialize_request(row)}


__all__ = ["router"]
