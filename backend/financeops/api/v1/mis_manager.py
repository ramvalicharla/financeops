from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
    require_finance_team,
)
from financeops.db.models.users import IamUser
from financeops.services.mis_service import (
    create_template,
    create_upload,
    get_template,
    get_upload,
    list_templates,
    list_uploads,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────

class CreateTemplateRequest(BaseModel):
    name: str
    entity_name: str
    template_data: dict[str, Any]
    description: str | None = None
    is_master: bool = False


class CreateUploadRequest(BaseModel):
    entity_name: str
    period_year: int
    period_month: int
    file_name: str
    file_hash: str
    template_id: UUID | None = None
    upload_notes: str | None = None
    parsed_data: dict[str, Any] | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_mis_template(
    body: CreateTemplateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """Create a new MIS template version (INSERT ONLY)."""
    template = await create_template(
        session,
        tenant_id=user.tenant_id,
        name=body.name,
        entity_name=body.entity_name,
        template_data=body.template_data,
        description=body.description,
        is_master=body.is_master,
        created_by=user.id,
    )
    await session.commit()
    return {
        "template_id": str(template.id),
        "name": template.name,
        "entity_name": template.entity_name,
        "version": template.version,
        "is_master": template.is_master,
        "sheet_count": template.sheet_count,
        "created_at": template.created_at.isoformat(),
    }


@router.get("/templates")
async def list_mis_templates(
    entity_name: str | None = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List MIS templates for the current tenant."""
    templates = await list_templates(
        session,
        tenant_id=user.tenant_id,
        entity_name=entity_name,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return {
        "templates": [
            {
                "template_id": str(t.id),
                "name": t.name,
                "entity_name": t.entity_name,
                "version": t.version,
                "is_master": t.is_master,
                "is_active": t.is_active,
                "sheet_count": t.sheet_count,
                "created_at": t.created_at.isoformat(),
            }
            for t in templates
        ],
        "count": len(templates),
    }


@router.get("/templates/{template_id}")
async def get_mis_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """Get a specific MIS template by ID."""
    template = await get_template(session, user.tenant_id, template_id)
    if template is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": str(template.id),
        "name": template.name,
        "entity_name": template.entity_name,
        "version": template.version,
        "is_master": template.is_master,
        "is_active": template.is_active,
        "sheet_count": template.sheet_count,
        "template_data": template.template_data,
        "description": template.description,
        "created_at": template.created_at.isoformat(),
    }


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def create_mis_upload(
    body: CreateUploadRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Record a new MIS file upload (INSERT ONLY)."""
    upload = await create_upload(
        session,
        tenant_id=user.tenant_id,
        entity_name=body.entity_name,
        period_year=body.period_year,
        period_month=body.period_month,
        file_name=body.file_name,
        file_hash=body.file_hash,
        uploaded_by=user.id,
        template_id=body.template_id,
        upload_notes=body.upload_notes,
        parsed_data=body.parsed_data,
    )
    await session.commit()
    return {
        "upload_id": str(upload.id),
        "entity_name": upload.entity_name,
        "period_year": upload.period_year,
        "period_month": upload.period_month,
        "file_name": upload.file_name,
        "status": upload.status,
        "created_at": upload.created_at.isoformat(),
    }


@router.get("/uploads")
async def list_mis_uploads(
    entity_name: str | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List MIS uploads for the current tenant."""
    uploads = await list_uploads(
        session,
        tenant_id=user.tenant_id,
        entity_name=entity_name,
        period_year=period_year,
        period_month=period_month,
        limit=limit,
        offset=offset,
    )
    return {
        "uploads": [
            {
                "upload_id": str(u.id),
                "entity_name": u.entity_name,
                "period_year": u.period_year,
                "period_month": u.period_month,
                "file_name": u.file_name,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in uploads
        ],
        "count": len(uploads),
    }


@router.get("/uploads/{upload_id}")
async def get_mis_upload(
    upload_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """Get a specific upload by ID."""
    upload = await get_upload(session, user.tenant_id, upload_id)
    if upload is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Upload not found")
    return {
        "upload_id": str(upload.id),
        "entity_name": upload.entity_name,
        "period_year": upload.period_year,
        "period_month": upload.period_month,
        "file_name": upload.file_name,
        "file_hash": upload.file_hash,
        "status": upload.status,
        "upload_notes": upload.upload_notes,
        "chain_hash": upload.chain_hash,
        "created_at": upload.created_at.isoformat(),
    }
