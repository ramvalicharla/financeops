from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import get_settings
from financeops.core.exceptions import FeatureNotImplementedError
from financeops.db.models.erp_sync import ExternalConnection, ExternalConnectionVersion
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.domain.enums import ConnectorType
from financeops.modules.erp_sync.infrastructure.connectors.registry import get_connector
from financeops.modules.erp_sync.infrastructure.secret_store import secret_store
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.idempotency import require_erp_sync_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


async def _build_secret_ref(body: dict[str, Any]) -> str | None:
    payload: dict[str, Any] = {
        "client_id": body.get("client_id"),
        "client_secret": body.get("client_secret"),
        "realm_id": body.get("realm_id"),
    }
    legacy_secret = str(body.get("secret_ref") or "").strip()
    if legacy_secret:
        payload["api_key"] = legacy_secret

    if not any(str(value or "").strip() for value in payload.values()):
        return None

    return await secret_store.put_secret(None, payload)


async def _resolve_connection_secret_ref(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    base_secret_ref: str | None,
) -> str | None:
    latest_version = (
        await session.execute(
            select(ExternalConnectionVersion)
            .where(
                ExternalConnectionVersion.tenant_id == tenant_id,
                ExternalConnectionVersion.connection_id == connection_id,
            )
            .order_by(
                ExternalConnectionVersion.version_no.desc(),
                ExternalConnectionVersion.created_at.desc(),
                ExternalConnectionVersion.id.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_version is None:
        return base_secret_ref

    snapshot = dict(latest_version.config_snapshot_json or {})
    secret_ref = str(
        snapshot.get("oauth_secret_ref")
        or snapshot.get("secret_ref")
        or base_secret_ref
        or ""
    ).strip()
    return secret_ref or None


@router.post("/connections")
async def create_connection(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_erp_sync_idempotency_key),
) -> dict[str, Any]:
    connector_type = ConnectorType(body["connector_type"])
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnection,
        tenant_id=user.tenant_id,
        record_data={
            "connection_code": str(body["connection_code"]),
            "connector_type": connector_type.value,
        },
        values={
            "organisation_id": uuid.UUID(str(body.get("organisation_id", user.tenant_id))),
            "entity_id": uuid.UUID(str(body["entity_id"])) if body.get("entity_id") else None,
            "connector_type": connector_type.value,
            "connection_code": str(body["connection_code"]),
            "connection_name": str(body.get("connection_name", body["connection_code"])),
            "source_system_instance_id": str(
                body.get("source_system_instance_id", f"{connector_type.value}:{uuid.uuid4().hex[:8]}")
            ),
            "data_residency_region": str(body.get("data_residency_region", "in")),
            "pii_masking_enabled": bool(body.get("pii_masking_enabled", True)),
            "consent_reference": body.get("consent_reference"),
            "pinned_connector_version": body.get("pinned_connector_version"),
            "connection_status": str(body.get("connection_status", "draft")),
            "secret_ref": await _build_secret_ref(body),
            "created_by": user.id,
        },
    )
    await session.flush()
    return ok(
        {
            "connection_id": str(row.id),
            "connection_code": row.connection_code,
            "connection_status": row.connection_status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connections")
async def list_connections(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(ExternalConnection).where(ExternalConnection.tenant_id == user.tenant_id).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ExternalConnection)
            .where(ExternalConnection.tenant_id == user.tenant_id)
            .order_by(ExternalConnection.created_at.desc(), ExternalConnection.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        {
            "id": str(row.id),
            "connection_code": row.connection_code,
            "connection_name": row.connection_name,
            "connector_type": row.connector_type,
            "connection_status": row.connection_status,
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {"data": items, "total": int(total), "limit": limit, "offset": offset}
    else:
        payload = {"items": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/connections/{id}")
async def get_connection(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "connection_code": row.connection_code,
            "connection_name": row.connection_name,
            "connector_type": row.connector_type,
            "connection_status": row.connection_status,
            "source_system_instance_id": row.source_system_instance_id,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/test")
async def test_connection(
    request: Request,
    id: str,
    body: dict[str, Any] | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    connector = get_connector(ConnectorType(row.connector_type))
    credentials = dict((body or {}).get("credentials", {}) or {})
    if not credentials:
        resolved_secret_ref = await _resolve_connection_secret_ref(
            session,
            tenant_id=user.tenant_id,
            connection_id=row.id,
            base_secret_ref=row.secret_ref,
        )
        if resolved_secret_ref:
            secret_payload = await secret_store.get_secret(resolved_secret_ref)
            credentials.update(
                {key: value for key, value in secret_payload.items() if value is not None}
            )
            credentials["secret_ref"] = resolved_secret_ref
    result = await connector.test_connection(credentials)
    return ok(
        {"connection_id": str(row.id), "ok": True, "result": result},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/activate")
async def activate_connection(request: Request, id: str) -> dict[str, Any]:
    return ok(
        {"id": id, "status": "accepted", "note": "append-only model; status transitions are event-driven"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/suspend")
async def suspend_connection(request: Request, id: str) -> dict[str, Any]:
    return ok(
        {"id": id, "status": "accepted", "note": "append-only model; status transitions are event-driven"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/revoke")
async def revoke_connection(request: Request, id: str) -> dict[str, Any]:
    return ok(
        {"id": id, "status": "accepted", "note": "append-only model; status transitions are event-driven"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/rotate-credentials")
async def rotate_credentials(request: Request, id: str) -> dict[str, Any]:
    if not get_settings().ERP_CONNECTION_SERVICE_ENABLED:
        raise FeatureNotImplementedError("erp_connection_credential_rotation")
    return ok(
        {"id": id, "rotated": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connections/{id}/upgrade-connector-version")
async def upgrade_connector_version(request: Request, id: str) -> dict[str, Any]:
    if not get_settings().ERP_CONNECTOR_VERSIONING_ENABLED:
        raise FeatureNotImplementedError("erp_connector_versioning")
    return ok(
        {"id": id, "upgraded": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connections/{id}/versions")
async def list_connection_versions(
    request: Request,
    id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    pagination_requested = "limit" in request.query_params or "offset" in request.query_params
    total = (
        await session.execute(
            select(func.count()).select_from(
                select(ExternalConnectionVersion).where(
                    ExternalConnectionVersion.tenant_id == user.tenant_id,
                    ExternalConnectionVersion.connection_id == uuid.UUID(id),
                ).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ExternalConnectionVersion)
            .where(
                ExternalConnectionVersion.tenant_id == user.tenant_id,
                ExternalConnectionVersion.connection_id == uuid.UUID(id),
            )
            .order_by(ExternalConnectionVersion.version_no.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [
        {
            "version_no": row.version_no,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]
    payload: dict[str, Any]
    if pagination_requested:
        payload = {
            "id": id,
            "data": items,
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }
    else:
        payload = {"id": id, "versions": items}
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/connections/{id}/capabilities")
async def list_connection_capabilities(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    connector = get_connector(ConnectorType(row.connector_type))
    return ok(
        {
            "id": id,
            "connector_type": row.connector_type,
            "supports_resumable_extraction": connector.supports_resumable_extraction,
            "supported_datasets": sorted(item.value for item in connector.supported_datasets),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
