from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.config import get_real_ip
from financeops.db.models.users import IamUser
from financeops.modules.digital_signoff.models import DirectorSignoff
from financeops.modules.digital_signoff.service import (
    complete_signoff,
    generate_certificate,
    initiate_signoff,
    list_signoffs,
    verify_signoff,
)
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/signoff", tags=["signoff"])


class InitiateRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    document_type: str
    document_id: uuid.UUID | None = None
    document_reference: str
    period: str
    signatory_user_id: uuid.UUID
    signatory_role: str
    document_content: str
    declaration_text: str


class CompleteRequest(BaseModel):
    totp_code: str


class VerifyRequest(BaseModel):
    content_hash: str


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
    raise HTTPException(
        status_code=422,
        detail="entity_id is required because no entity is configured for this user",
    )


def _serialize(row: DirectorSignoff) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "entity_id": str(row.entity_id),
        "document_type": row.document_type,
        "document_id": str(row.document_id) if row.document_id else None,
        "document_reference": row.document_reference,
        "period": row.period,
        "signatory_user_id": str(row.signatory_user_id),
        "signatory_name": row.signatory_name,
        "signatory_role": row.signatory_role,
        "mfa_verified": row.mfa_verified,
        "mfa_verified_at": row.mfa_verified_at.isoformat() if row.mfa_verified_at else None,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "declaration_text": row.declaration_text,
        "content_hash": row.content_hash,
        "signature_hash": row.signature_hash,
        "status": row.status,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/initiate")
async def initiate_endpoint(
    body: InitiateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, body.entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    row = await initiate_signoff(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        document_type=body.document_type,
        document_reference=body.document_reference,
        period=body.period,
        signatory_user_id=body.signatory_user_id,
        signatory_role=body.signatory_role,
        document_content=body.document_content,
        declaration_text=body.declaration_text,
        document_id=body.document_id,
    )
    return _serialize(row)


@router.post("/{signoff_id}/sign")
async def complete_endpoint(
    signoff_id: uuid.UUID,
    body: CompleteRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "")
    current = (
        await session.execute(
            select(DirectorSignoff).where(
                DirectorSignoff.id == signoff_id,
                DirectorSignoff.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="Signoff request not found")
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await complete_signoff(
        session,
        tenant_id=user.tenant_id,
        signoff_id=signoff_id,
        signatory_user_id=user.id,
        totp_code=body.totp_code,
        ip_address=ip,
        user_agent=user_agent,
    )
    return _serialize(row)


@router.get("/{signoff_id}/certificate")
async def certificate_endpoint(
    signoff_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    payload = await generate_certificate(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        signoff_id=signoff_id,
    )
    return {
        "certificate_number": payload["certificate_number"],
        "document_reference": payload["document_reference"],
        "period": payload["period"],
        "signatory_name": payload["signatory_name"],
        "signatory_role": payload["signatory_role"],
        "signed_at": payload["signed_at"].isoformat() if payload["signed_at"] else None,
        "content_hash": payload["content_hash"],
        "signature_hash": payload["signature_hash"],
        "is_valid": payload["is_valid"],
        "declaration_text": payload["declaration_text"],
    }


@router.get("", response_model=Paginated[dict])
async def list_endpoint(
    entity_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    payload = await list_signoffs(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        limit=limit,
        offset=offset,
    )
    return Paginated[dict](data=[_serialize(row) for row in payload["data"]], total=payload["total"], limit=payload["limit"], offset=payload["offset"])


@router.post("/{signoff_id}/verify")
async def verify_endpoint(
    signoff_id: uuid.UUID,
    body: VerifyRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    match = (
        await session.execute(
            select(DirectorSignoff).where(
                DirectorSignoff.id == signoff_id,
                DirectorSignoff.tenant_id == user.tenant_id,
                DirectorSignoff.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if match is None:
        return {"is_valid": False}
    return {
        "is_valid": verify_signoff(
            body.content_hash,
            match.signatory_user_id,
            match.signed_at,
            match,
        )
    }


__all__ = ["router"]
