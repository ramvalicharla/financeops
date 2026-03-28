from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_tenant_id
from financeops.config import limiter
from financeops.db.session import get_raw_session
from financeops.modules.accounting_ingestion.application.email_ingestion_service import (
    ingest_email,
)
from financeops.modules.accounting_ingestion.application.vendor_portal_service import (
    create_submission,
    get_submission_status,
)

router = APIRouter(prefix="/ingestion", tags=["Accounting Ingestion"])
public_router = APIRouter(prefix="/ingestion", tags=["Accounting Ingestion Public"])


class EmailIngestRequest(BaseModel):
    message_id: str
    sender_email: str
    sender_name: str | None = None
    subject: str | None = None
    sender_whitelist: list[str] | None = None
    entity_routing_id: uuid.UUID | None = None
    raw_metadata: dict[str, Any] | None = None


class EmailIngestResponse(BaseModel):
    message_id: uuid.UUID
    status: str
    sender_whitelisted: bool
    attachment_count: int


class PortalSubmitResponse(BaseModel):
    reference_id: str
    status: str
    message: str


class PortalStatusResponse(BaseModel):
    found: bool
    reference_id: str
    status: str | None = None
    submitted_at: str | None = None
    filename: str | None = None


def _vendor_submit_rate_key(request: Request) -> str:
    email = request.headers.get("x-submitter-email", "").strip().lower()
    tenant = request.headers.get("x-tenant-id", "").strip().lower()
    client = request.client.host if request.client else "unknown"
    return f"{client}:{tenant}:{email or 'unknown'}"


async def _get_tenant_from_api_key(
    x_api_key: Annotated[str, Header(..., alias="X-API-Key")],
    x_tenant_id: Annotated[str, Header(..., alias="X-Tenant-ID")],
) -> uuid.UUID:
    if not x_api_key.strip():
        raise HTTPException(status_code=401, detail="Missing API key")
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID") from exc


@limiter.limit("30/minute")
@router.post("/email/ingest", response_model=EmailIngestResponse)
async def email_ingest_endpoint(
    request: Request,
    body: EmailIngestRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
) -> EmailIngestResponse:
    del request
    row = await ingest_email(
        session,
        tenant_id=tenant_id,
        message_id=body.message_id,
        sender_email=body.sender_email,
        sender_name=body.sender_name,
        subject=body.subject,
        attachment_bytes_list=[],
        raw_metadata=body.raw_metadata,
        sender_whitelist=body.sender_whitelist or [],
        entity_routing_id=body.entity_routing_id,
    )
    await session.flush()
    return EmailIngestResponse(
        message_id=row.id,
        status=row.processing_status,
        sender_whitelisted=row.sender_whitelisted,
        attachment_count=row.attachment_count,
    )


@limiter.limit("10/minute", key_func=_vendor_submit_rate_key)
@public_router.post("/vendor-portal/submit", response_model=PortalSubmitResponse)
async def vendor_portal_submit_endpoint(
    request: Request,
    file: UploadFile = File(...),
    submitter_email: str = Form(...),
    submitter_name: str | None = Form(default=None),
    entity_id: str | None = Form(default=None),
    session: AsyncSession = Depends(get_raw_session),
    tenant_id: uuid.UUID = Depends(_get_tenant_from_api_key),
) -> PortalSubmitResponse:
    del request
    parsed_entity_id: uuid.UUID | None = None
    if entity_id:
        try:
            parsed_entity_id = uuid.UUID(entity_id)
        except ValueError:
            parsed_entity_id = None

    file_bytes = await file.read()
    row = await create_submission(
        session,
        tenant_id=tenant_id,
        submitter_email=submitter_email,
        submitter_name=submitter_name,
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        entity_id=parsed_entity_id,
    )
    await session.flush()
    return PortalSubmitResponse(
        reference_id=row.reference_id,
        status=row.status,
        message=f"Submission received. Reference ID: {row.reference_id}",
    )


@limiter.limit("30/minute")
@public_router.get("/vendor-portal/status/{reference_id}", response_model=PortalStatusResponse)
async def vendor_portal_status_endpoint(
    request: Request,
    reference_id: str,
    session: AsyncSession = Depends(get_raw_session),
    tenant_id: uuid.UUID = Depends(_get_tenant_from_api_key),
) -> PortalStatusResponse:
    del request
    result = await get_submission_status(
        session,
        reference_id=reference_id,
        tenant_id=tenant_id,
    )
    return PortalStatusResponse(**result)

