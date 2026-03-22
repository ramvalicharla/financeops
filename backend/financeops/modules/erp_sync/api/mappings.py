from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import ExternalMappingDefinition, ExternalMappingVersion
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.mapping_service import MappingService
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.post("/mappings")
async def create_mapping(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = MappingService(session)
    row = await service.create_mapping_definition(
        tenant_id=user.tenant_id,
        organisation_id=uuid.UUID(str(body.get("organisation_id", user.tenant_id))),
        mapping_code=str(body["mapping_code"]),
        mapping_name=str(body.get("mapping_name", body["mapping_code"])),
        dataset_type=str(body["dataset_type"]),
        created_by=user.id,
        status=str(body.get("status", "draft")),
    )
    await session.flush()
    return ok(
        {
            "mapping_definition_id": str(row.id),
            "mapping_code": row.mapping_code,
            "mapping_status": row.mapping_status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/mappings")
async def list_mappings(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalMappingDefinition)
            .where(ExternalMappingDefinition.tenant_id == user.tenant_id)
            .order_by(ExternalMappingDefinition.created_at.desc(), ExternalMappingDefinition.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "mapping_code": row.mapping_code,
                    "mapping_name": row.mapping_name,
                    "dataset_type": row.dataset_type,
                    "mapping_status": row.mapping_status,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/mappings/{id}")
async def get_mapping(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalMappingDefinition).where(
                ExternalMappingDefinition.tenant_id == user.tenant_id,
                ExternalMappingDefinition.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "mapping_code": row.mapping_code,
            "mapping_name": row.mapping_name,
            "dataset_type": row.dataset_type,
            "mapping_status": row.mapping_status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/mappings/{id}/versions")
async def create_mapping_version(
    request: Request,
    id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = MappingService(session)
    row = await service.create_mapping_version(
        tenant_id=user.tenant_id,
        mapping_definition_id=uuid.UUID(id),
        mapping_payload_json=dict(body.get("mapping_payload_json", {})),
        created_by=user.id,
        activate=bool(body.get("activate", False)),
        supersedes_id=uuid.UUID(str(body["supersedes_id"])) if body.get("supersedes_id") else None,
    )
    await session.flush()
    return ok(
        {
            "id": id,
            "mapping_version_id": str(row.id),
            "version_no": row.version_no,
            "version_token": row.version_token,
            "status": row.status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/mappings/{id}/versions")
async def list_mapping_versions(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalMappingVersion)
            .where(
                ExternalMappingVersion.tenant_id == user.tenant_id,
                ExternalMappingVersion.mapping_definition_id == uuid.UUID(id),
            )
            .order_by(ExternalMappingVersion.version_no.desc(), ExternalMappingVersion.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "id": id,
            "versions": [
                {
                    "id": str(row.id),
                    "version_no": row.version_no,
                    "version_token": row.version_token,
                    "status": row.status,
                    "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
                }
                for row in rows
            ],
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/mappings/{id}/versions/{vid}/activate")
async def activate_mapping_version(
    request: Request,
    id: str,
    vid: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    source = (
        await session.execute(
            select(ExternalMappingVersion).where(
                ExternalMappingVersion.tenant_id == user.tenant_id,
                ExternalMappingVersion.mapping_definition_id == uuid.UUID(id),
                ExternalMappingVersion.id == uuid.UUID(vid),
            )
        )
    ).scalar_one()
    if source.status == "active":
        return ok(
            {
                "id": id,
                "version_id": vid,
                "status": "active",
                "idempotent_replay": True,
            },
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")

    service = MappingService(session)
    activated = await service.create_mapping_version(
        tenant_id=user.tenant_id,
        mapping_definition_id=uuid.UUID(id),
        mapping_payload_json=dict(source.mapping_payload_json or {}),
        created_by=user.id,
        activate=True,
        supersedes_id=source.id,
    )
    await session.flush()
    return ok(
        {
            "id": id,
            "version_id": str(activated.id),
            "status": activated.status,
            "version_token": activated.version_token,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
