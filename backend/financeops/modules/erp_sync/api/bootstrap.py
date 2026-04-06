from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.core.exceptions import NotFoundError
from financeops.db.models.erp_sync import (
    ExternalConnection,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
)
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.connection_service import ConnectionService
from financeops.modules.erp_sync.application.connection_service import resolve_connection_runtime_state
from financeops.modules.erp_sync.application.mapping_service import MappingService
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.response import ok
from financeops.shared_kernel.tokens import build_token

router = APIRouter(prefix="/bootstrap", tags=["ERP Sync Bootstrap"])


def _default_mapping_code(connection_id: uuid.UUID, dataset_type: str) -> str:
    return f"bootstrap-map-{dataset_type}-{str(connection_id)[:8]}"


def _default_definition_code(connection_id: uuid.UUID, dataset_type: str) -> str:
    return f"bootstrap-sync-{dataset_type}-{str(connection_id)[:8]}"


@router.post("/test-ready")
async def ensure_test_ready_sync_path(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    connection_id = uuid.UUID(str(body["connection_id"]))
    dataset_type = str(body["dataset_type"])
    connection = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == connection_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise NotFoundError("Connection not found")

    _, runtime_state = await resolve_connection_runtime_state(session, connection=connection)
    current_status = str(runtime_state.get("connection_status") or connection.connection_status).strip().lower()
    if bool(body.get("activate_connection", True)) and current_status != "active":
        connection_service = ConnectionService(session)
        await connection_service.set_connection_status(
            tenant_id=user.tenant_id,
            connection_id=connection.id,
            new_status="active",
            actor_user_id=user.id,
        )
        _, runtime_state = await resolve_connection_runtime_state(session, connection=connection)

    mapping_service = MappingService(session)
    try:
        mapping_resolution = await mapping_service.get_active_mapping_for_connection(
            tenant_id=user.tenant_id,
            connection_id=connection.id,
            dataset_type=dataset_type,
        )
    except NotFoundError:
        mapping_definition = await mapping_service.create_mapping_definition(
            tenant_id=user.tenant_id,
            organisation_id=connection.organisation_id,
            mapping_code=str(body.get("mapping_code") or _default_mapping_code(connection.id, dataset_type)),
            mapping_name=str(body.get("mapping_name") or f"{dataset_type} bootstrap mapping"),
            dataset_type=dataset_type,
            created_by=user.id,
            status="active",
        )
        mapping_version = await mapping_service.create_mapping_version(
            tenant_id=user.tenant_id,
            mapping_definition_id=mapping_definition.id,
            mapping_payload_json=dict(body.get("mapping_payload_json", {})),
            created_by=user.id,
            activate=True,
        )
        mapping_resolution = {
            "mapping_definition_id": str(mapping_definition.id),
            "mapping_version_id": str(mapping_version.id),
            "mapping_version_token": mapping_version.version_token,
        }

    definition = (
        await session.execute(
            select(ExternalSyncDefinition)
            .where(
                ExternalSyncDefinition.tenant_id == user.tenant_id,
                ExternalSyncDefinition.connection_id == connection.id,
                ExternalSyncDefinition.dataset_type == dataset_type,
                ExternalSyncDefinition.definition_status == "active",
            )
            .order_by(ExternalSyncDefinition.created_at.desc(), ExternalSyncDefinition.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    version: ExternalSyncDefinitionVersion | None = None
    if definition is not None:
        version = (
            await session.execute(
                select(ExternalSyncDefinitionVersion)
                .where(
                    ExternalSyncDefinitionVersion.tenant_id == user.tenant_id,
                    ExternalSyncDefinitionVersion.sync_definition_id == definition.id,
                    ExternalSyncDefinitionVersion.status == "active",
                )
                .order_by(
                    ExternalSyncDefinitionVersion.version_no.desc(),
                    ExternalSyncDefinitionVersion.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    if definition is None:
        definition = await AuditWriter.insert_financial_record(
            session,
            model_class=ExternalSyncDefinition,
            tenant_id=user.tenant_id,
            record_data={
                "organisation_id": str(connection.organisation_id),
                "definition_code": str(
                    body.get("definition_code") or _default_definition_code(connection.id, dataset_type)
                ),
                "dataset_type": dataset_type,
            },
            values={
                "organisation_id": uuid.UUID(str(body.get("organisation_id", connection.organisation_id))),
                "entity_id": uuid.UUID(str(body["entity_id"])) if body.get("entity_id") else connection.entity_id,
                "connection_id": connection.id,
                "definition_code": str(
                    body.get("definition_code") or _default_definition_code(connection.id, dataset_type)
                ),
                "definition_name": str(body.get("definition_name") or f"{dataset_type} bootstrap sync"),
                "dataset_type": dataset_type,
                "sync_mode": str(body.get("sync_mode", "full")),
                "definition_status": "active",
                "created_by": user.id,
            },
        )

    if version is None:
        max_version = (
            await session.execute(
                select(func.max(ExternalSyncDefinitionVersion.version_no)).where(
                    ExternalSyncDefinitionVersion.tenant_id == user.tenant_id,
                    ExternalSyncDefinitionVersion.sync_definition_id == definition.id,
                )
            )
        ).scalar_one_or_none()
        next_version = int(max_version or 0) + 1
        period_resolution_json = dict(body.get("period_resolution_json", {}))
        extraction_scope_json = dict(body.get("extraction_scope_json", {}))
        version_token = build_token(
            {
                "sync_definition_id": str(definition.id),
                "version_no": next_version,
                "period_resolution_json": period_resolution_json,
                "extraction_scope_json": extraction_scope_json,
            }
        )
        version = await AuditWriter.insert_financial_record(
            session,
            model_class=ExternalSyncDefinitionVersion,
            tenant_id=user.tenant_id,
            record_data={
                "sync_definition_id": str(definition.id),
                "version_no": next_version,
                "version_token": version_token,
            },
            values={
                "sync_definition_id": definition.id,
                "version_no": next_version,
                "version_token": version_token,
                "period_resolution_json": period_resolution_json,
                "extraction_scope_json": extraction_scope_json,
                "supersedes_id": None,
                "status": "active",
                "created_by": user.id,
            },
        )

    await session.flush()
    return ok(
        {
            "connection_id": str(connection.id),
            "connection_status": str(runtime_state.get("connection_status") or connection.connection_status),
            "mapping_definition_id": str(mapping_resolution["mapping_definition_id"]),
            "mapping_version_id": str(mapping_resolution["mapping_version_id"]),
            "sync_definition_id": str(definition.id),
            "sync_definition_version_id": str(version.id),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
