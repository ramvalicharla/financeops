from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.db.models.erp_sync import (
    ExternalConnection,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
    ExternalSyncRun,
)
from financeops.db.models.users import IamUser
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.response import ok
from financeops.shared_kernel.tokens import build_token

router = APIRouter()

_DATASET_TYPE = "journal_export"


@router.post("/sync-runs/export-journals", status_code=status.HTTP_201_CREATED)
async def export_journals(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    """Create a sync run record for a journal export operation.

    Body:
        connection_id: UUID
        sync_definition_id: UUID
        sync_definition_version_id: UUID
        journal_ids: list[str] (optional)
        reporting_period_label: str (optional)
    """
    connection_id = uuid.UUID(str(body["connection_id"]))
    sync_definition_id = uuid.UUID(str(body["sync_definition_id"]))
    sync_definition_version_id = uuid.UUID(str(body["sync_definition_version_id"]))

    connection = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == connection_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connection_not_found")

    definition = (
        await session.execute(
            select(ExternalSyncDefinition).where(
                ExternalSyncDefinition.tenant_id == user.tenant_id,
                ExternalSyncDefinition.id == sync_definition_id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sync_definition_not_found")

    version = (
        await session.execute(
            select(ExternalSyncDefinitionVersion).where(
                ExternalSyncDefinitionVersion.tenant_id == user.tenant_id,
                ExternalSyncDefinitionVersion.id == sync_definition_version_id,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sync_definition_version_not_found")

    idempotency_key = str(
        body.get("idempotency_key")
        or f"journal-export:{user.tenant_id}:{connection_id}:{uuid.uuid4()}"
    )
    run_token = build_token(
        {
            "tenant_id": str(user.tenant_id),
            "connection_id": str(connection_id),
            "sync_definition_id": str(sync_definition_id),
            "idempotency_key": idempotency_key,
            "dataset_type": _DATASET_TYPE,
        }
    )

    sync_run = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalSyncRun,
        tenant_id=user.tenant_id,
        record_data={
            "organisation_id": str(connection.organisation_id),
            "connection_id": str(connection_id),
            "sync_definition_id": str(sync_definition_id),
            "dataset_type": _DATASET_TYPE,
            "run_token": run_token,
        },
        values={
            "organisation_id": connection.organisation_id,
            "entity_id": connection.entity_id,
            "connection_id": connection_id,
            "sync_definition_id": sync_definition_id,
            "sync_definition_version_id": sync_definition_version_id,
            "dataset_type": _DATASET_TYPE,
            "reporting_period_label": str(body.get("reporting_period_label") or ""),
            "run_token": run_token,
            "idempotency_key": idempotency_key,
            "run_status": "created",
            "validation_summary_json": {
                "journal_ids": list(body.get("journal_ids") or []),
            },
            "created_by": user.id,
        },
    )
    await session.flush()

    return ok(
        {
            "status": "created",
            "record_refs": {
                "sync_run_id": str(sync_run.id),
                "run_token": sync_run.run_token,
                "dataset_type": _DATASET_TYPE,
            },
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
