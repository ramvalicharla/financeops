from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
    require_org_setup,
)
from financeops.db.models.tenants import IamTenant
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
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/audit", tags=["audit_portal"])


class GrantAccessRequest(BaseModel):
    entity_id: uuid.UUID | None = None
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
        "entity_id": str(row.entity_id),
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
        "entity_id": str(row.entity_id),
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


async def _resolve_entity_id(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if entities:
        return entities[0].id
    raise HTTPException(status_code=422, detail="entity_id is required because no entity is configured for this user")


@router.post("/access/grant")
async def grant_access_endpoint(
    body: GrantAccessRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _tenant: IamTenant = Depends(require_org_setup),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, body.entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
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
        entity_id=resolved_entity_id,
        access_level=body.access_level,
    )
    await seed_pbc_checklist(
        session,
        access_id=access.id,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
    )
    return {"access": _serialize_access(access), "token": plain_token}


@router.get("/access", response_model=Paginated[dict])
async def list_access_endpoint(
    entity_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _tenant: IamTenant = Depends(require_org_setup),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    payload = await list_access(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        limit=limit,
        offset=offset,
    )
    return Paginated[dict](data=[_serialize_access(row) for row in payload["data"]], total=payload["total"], limit=payload["limit"], offset=payload["offset"])


@router.patch("/access/{access_id}/revoke")
async def revoke_access_endpoint(
    access_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _tenant: IamTenant = Depends(require_org_setup),
) -> dict:
    current = (
        await session.execute(
            select(AuditorPortalAccess).where(
                AuditorPortalAccess.id == access_id,
                AuditorPortalAccess.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="Access record not found")
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await revoke_access(session, tenant_id=user.tenant_id, access_id=access_id)
    return _serialize_access(row)


@router.get("/{engagement_id}/pbc")
async def pbc_tracker_endpoint(
    engagement_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _tenant: IamTenant = Depends(require_org_setup),
) -> dict:
    access = (
        await session.execute(
            select(AuditorPortalAccess).where(
                AuditorPortalAccess.id == engagement_id,
                AuditorPortalAccess.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=404, detail="Audit engagement not found")
    await assert_entity_access(session, user.tenant_id, access.entity_id, user.id, user.role)
    payload = await get_pbc_tracker(
        session,
        access_id=engagement_id,
        tenant_id=user.tenant_id,
        entity_id=access.entity_id,
    )
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
    _tenant: IamTenant = Depends(require_org_setup),
) -> dict:
    access = (
        await session.execute(
            select(AuditorPortalAccess).where(
                AuditorPortalAccess.id == engagement_id,
                AuditorPortalAccess.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=404, detail="Audit engagement not found")
    await assert_entity_access(session, user.tenant_id, access.entity_id, user.id, user.role)
    row = await respond_to_request(
        session,
        tenant_id=user.tenant_id,
        entity_id=access.entity_id,
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
            .where(
                AuditorRequest.access_id == access.id,
                AuditorRequest.tenant_id == access.tenant_id,
                AuditorRequest.entity_id == access.entity_id,
            )
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
