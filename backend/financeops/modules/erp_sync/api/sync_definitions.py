from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import (
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
)
from financeops.db.models.users import IamUser
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.tokens import build_token
from financeops.shared_kernel.response import ok
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text

router = APIRouter()


@router.post("/sync-definitions")
async def create_sync_definition(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    definition = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncDefinition,
        tenant_id=user.tenant_id,
        record_data={
            "organisation_id": str(body.get("organisation_id", user.tenant_id)),
            "definition_code": str(body["definition_code"]),
            "dataset_type": str(body["dataset_type"]),
        },
        values={
            "organisation_id": uuid.UUID(str(body.get("organisation_id", user.tenant_id))),
            "entity_id": uuid.UUID(str(body["entity_id"])) if body.get("entity_id") else None,
            "connection_id": uuid.UUID(str(body["connection_id"])),
            "definition_code": str(body["definition_code"]),
            "definition_name": str(body.get("definition_name", body["definition_code"])),
            "dataset_type": str(body["dataset_type"]),
            "sync_mode": str(body.get("sync_mode", "full")),
            "definition_status": str(body.get("definition_status", "active")),
            "created_by": user.id,
        },
    )
    version_token = build_token(
        {
            "sync_definition_id": str(definition.id),
            "period_resolution_json": body.get("period_resolution_json", {}),
            "extraction_scope_json": body.get("extraction_scope_json", {}),
        }
    )
    version = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncDefinitionVersion,
        tenant_id=user.tenant_id,
        record_data={
            "sync_definition_id": str(definition.id),
            "version_no": 1,
            "version_token": version_token,
        },
        values={
            "sync_definition_id": definition.id,
            "version_no": 1,
            "version_token": version_token,
            "period_resolution_json": dict(body.get("period_resolution_json", {})),
            "extraction_scope_json": dict(body.get("extraction_scope_json", {})),
            "supersedes_id": None,
            "status": "active",
            "created_by": user.id,
        },
    )
    await session.flush()
    return ok(
        {
            "sync_definition_id": str(definition.id),
            "sync_definition_version_id": str(version.id),
            "version_token": version.version_token,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/sync-definitions")
async def list_sync_definitions(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalSyncDefinition)
            .where(ExternalSyncDefinition.tenant_id == user.tenant_id)
            .order_by(ExternalSyncDefinition.created_at.desc(), ExternalSyncDefinition.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "definition_code": row.definition_code,
                    "dataset_type": row.dataset_type,
                    "sync_mode": row.sync_mode,
                    "definition_status": row.definition_status,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/sync-definitions/{id}")
async def get_sync_definition(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalSyncDefinition).where(
                ExternalSyncDefinition.tenant_id == user.tenant_id,
                ExternalSyncDefinition.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "dataset_type": row.dataset_type,
            "sync_mode": row.sync_mode,
            "definition_status": row.definition_status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync-definitions/{id}/supersede")
async def supersede_sync_definition(
    request: Request,
    id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    max_version = (
        await session.execute(
            select(func.max(ExternalSyncDefinitionVersion.version_no)).where(
                ExternalSyncDefinitionVersion.tenant_id == user.tenant_id,
                ExternalSyncDefinitionVersion.sync_definition_id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    next_version = int(max_version or 0) + 1
    period_resolution_json = dict(body.get("period_resolution_json", {}))
    extraction_scope_json = dict(body.get("extraction_scope_json", {}))
    version_token = sha256_hex_text(
        canonical_json_dumps(
            {
                "sync_definition_id": id,
                "version_no": next_version,
                "period_resolution_json": period_resolution_json,
                "extraction_scope_json": extraction_scope_json,
            }
        )
    )
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncDefinitionVersion,
        tenant_id=user.tenant_id,
        record_data={"sync_definition_id": id, "version_no": next_version, "version_token": version_token},
        values={
            "sync_definition_id": uuid.UUID(id),
            "version_no": next_version,
            "version_token": version_token,
            "period_resolution_json": period_resolution_json,
            "extraction_scope_json": extraction_scope_json,
            "supersedes_id": uuid.UUID(str(body["supersedes_id"])) if body.get("supersedes_id") else None,
            "status": str(body.get("status", "candidate")),
            "created_by": user.id,
        },
    )
    await session.flush()
    return ok(
        {"id": id, "sync_definition_version_id": str(row.id), "status": row.status},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync-definitions/{id}/retire")
async def retire_sync_definition(request: Request, id: str) -> dict[str, Any]:
    return ok(
        {"id": id, "status": "accepted", "note": "append-only model; retirement is represented by new version rows"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
