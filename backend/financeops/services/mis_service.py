from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisTemplate, MisUpload
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)


async def create_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    entity_name: str,
    template_data: dict[str, Any],
    description: str | None = None,
    is_master: bool = False,
    created_by: uuid.UUID,
) -> MisTemplate:
    """
    Create a new MIS template version (INSERT ONLY).
    Deactivates any previous active template for the same entity.
    """
    # Get current version number for this entity
    result = await session.execute(
        select(MisTemplate.version)
        .where(
            MisTemplate.tenant_id == tenant_id, MisTemplate.entity_name == entity_name
        )
        .order_by(desc(MisTemplate.created_at))
        .limit(1)
    )
    last_version = result.scalar()
    next_version = (last_version or 0) + 1
    sheet_count = len(template_data.get("sheets", []))
    entity_slug = "_".join(entity_name.lower().split())[:90] or "entity"
    template_code = f"legacy_{entity_slug}_{next_version}"

    template = await AuditWriter.insert_financial_record(
        session,
        model_class=MisTemplate,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "name": name,
            "entity_name": entity_name,
            "version": next_version,
            "is_master": is_master,
            "is_active": True,
            "sheet_count": sheet_count,
            "created_by": str(created_by),
            "organisation_id": str(tenant_id),
            "template_code": template_code,
            "template_name": name,
            "template_type": "custom",
            "status": "active",
        },
        values={
            "name": name,
            "description": description,
            "entity_name": entity_name,
            "version": next_version,
            "is_master": is_master,
            "is_active": True,
            "template_data": template_data,
            "sheet_count": sheet_count,
            "created_by": created_by,
            # Phase 1F.1 canonical columns required by mis_templates.
            "organisation_id": tenant_id,
            "template_code": template_code,
            "template_name": name,
            "template_type": "custom",
            "status": "active",
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="mis.template.created",
            resource_type="mis_template",
            resource_name=name,
            new_value={
                "entity_name": entity_name,
                "version": next_version,
                "is_master": is_master,
            },
        ),
    )
    log.info(
        "MisTemplate created: tenant=%s entity=%s version=%d",
        str(tenant_id)[:8], entity_name, next_version,
    )
    return template


async def get_template(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> MisTemplate | None:
    result = await session.execute(
        select(MisTemplate).where(
            MisTemplate.id == template_id,
            MisTemplate.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_templates(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_name: str | None = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[MisTemplate]:
    stmt = select(MisTemplate).where(MisTemplate.tenant_id == tenant_id)
    if entity_name:
        stmt = stmt.where(MisTemplate.entity_name == entity_name)
    if active_only:
        stmt = stmt.where(MisTemplate.is_active.is_(True))
    stmt = stmt.order_by(desc(MisTemplate.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_upload(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_name: str,
    period_year: int,
    period_month: int,
    file_name: str,
    file_hash: str,
    uploaded_by: uuid.UUID,
    template_id: uuid.UUID | None = None,
    upload_notes: str | None = None,
    parsed_data: dict[str, Any] | None = None,
) -> MisUpload:
    """Create a new MIS upload record (INSERT ONLY)."""
    upload = await AuditWriter.insert_financial_record(
        session,
        model_class=MisUpload,
        tenant_id=tenant_id,
        record_data={
            "tenant_id": str(tenant_id),
            "entity_name": entity_name,
            "period_year": period_year,
            "period_month": period_month,
            "file_name": file_name,
            "file_hash": file_hash,
            "uploaded_by": str(uploaded_by),
        },
        values={
            "template_id": template_id,
            "entity_name": entity_name,
            "period_year": period_year,
            "period_month": period_month,
            "file_name": file_name,
            "file_hash": file_hash,
            "status": "pending",
            "upload_notes": upload_notes,
            "parsed_data": parsed_data,
            "uploaded_by": uploaded_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=uploaded_by,
            action="mis.upload.created",
            resource_type="mis_upload",
            resource_name=file_name,
            new_value={
                "entity_name": entity_name,
                "period_year": period_year,
                "period_month": period_month,
            },
        ),
    )
    return upload


async def list_uploads(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_name: str | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MisUpload]:
    stmt = select(MisUpload).where(MisUpload.tenant_id == tenant_id)
    if entity_name:
        stmt = stmt.where(MisUpload.entity_name == entity_name)
    if period_year is not None:
        stmt = stmt.where(MisUpload.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(MisUpload.period_month == period_month)
    stmt = stmt.order_by(desc(MisUpload.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_upload(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    upload_id: uuid.UUID,
) -> MisUpload | None:
    result = await session.execute(
        select(MisUpload).where(
            MisUpload.id == upload_id,
            MisUpload.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()

