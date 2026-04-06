from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.erp_sync import ExternalConnection, ExternalConnectionVersion
from financeops.modules.erp_sync.infrastructure.secret_store import secret_store
from financeops.services.audit_writer import AuditWriter

_ALLOWED_CREDENTIAL_KEYS: tuple[str, ...] = (
    "api_key",
    "client_id",
    "client_secret",
    "access_token",
    "refresh_token",
    "token_expires_at",
    "realm_id",
    "organization_id",
    "use_sandbox",
)


def _isoformat_if_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _build_base_runtime_snapshot(connection: ExternalConnection) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "connection_status": getattr(connection, "connection_status", "draft"),
        "connector_type": getattr(connection, "connector_type", ""),
    }
    pinned_connector_version = getattr(connection, "pinned_connector_version", None)
    if pinned_connector_version:
        snapshot["pinned_connector_version"] = pinned_connector_version
    secret_ref = getattr(connection, "secret_ref", None)
    if secret_ref:
        snapshot["secret_ref"] = secret_ref
        snapshot["oauth_secret_ref"] = secret_ref
    token_expires_at = _isoformat_if_datetime(getattr(connection, "token_expires_at", None))
    if token_expires_at:
        snapshot["token_expires_at"] = token_expires_at
    token_refreshed_at = _isoformat_if_datetime(getattr(connection, "token_refreshed_at", None))
    if token_refreshed_at:
        snapshot["token_refreshed_at"] = token_refreshed_at
    oauth_scopes = getattr(connection, "oauth_scopes", None)
    if oauth_scopes:
        snapshot["oauth_scopes"] = oauth_scopes
    return snapshot


def merge_connection_runtime_snapshot(
    connection: ExternalConnection,
    latest_version: ExternalConnectionVersion | None,
) -> dict[str, Any]:
    snapshot = _build_base_runtime_snapshot(connection)
    latest_snapshot = getattr(latest_version, "config_snapshot_json", None)
    if latest_snapshot:
        snapshot.update(dict(latest_snapshot or {}))
    connection_status = getattr(connection, "connection_status", "draft")
    connector_type = getattr(connection, "connector_type", "")
    secret_ref = getattr(connection, "secret_ref", None)
    snapshot.setdefault("connection_status", connection_status)
    snapshot.setdefault("connector_type", connector_type)
    if secret_ref:
        snapshot.setdefault("secret_ref", secret_ref)
        snapshot.setdefault("oauth_secret_ref", secret_ref)
    return snapshot


async def get_latest_connection_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> ExternalConnectionVersion | None:
    return (
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


async def resolve_connection_runtime_state(
    session: AsyncSession,
    *,
    connection: ExternalConnection,
) -> tuple[ExternalConnectionVersion | None, dict[str, Any]]:
    tenant_id = getattr(connection, "tenant_id", None) or getattr(connection, "organisation_id", None)
    if tenant_id is None:
        return None, merge_connection_runtime_snapshot(connection, None)
    latest = await get_latest_connection_version(
        session,
        tenant_id=tenant_id,
        connection_id=connection.id,
    )
    return latest, merge_connection_runtime_snapshot(connection, latest)


class ConnectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_connection(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> ExternalConnection:
        row = (
            await self._session.execute(
                select(ExternalConnection).where(
                    ExternalConnection.tenant_id == tenant_id,
                    ExternalConnection.id == connection_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Connection not found")
        return row

    async def _get_latest_version(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> ExternalConnectionVersion | None:
        return await get_latest_connection_version(
            self._session,
            tenant_id=tenant_id,
            connection_id=connection_id,
        )

    async def _append_version(
        self,
        *,
        connection: ExternalConnection,
        created_by: uuid.UUID,
        snapshot_updates: Mapping[str, Any] | None = None,
        status: str = "active",
    ) -> ExternalConnectionVersion:
        latest, snapshot = await resolve_connection_runtime_state(
            self._session,
            connection=connection,
        )
        max_version_no = (
            await self._session.execute(
                select(func.max(ExternalConnectionVersion.version_no)).where(
                    ExternalConnectionVersion.tenant_id == connection.tenant_id,
                    ExternalConnectionVersion.connection_id == connection.id,
                )
            )
        ).scalar_one_or_none()
        next_version_no = int(max_version_no or 0) + 1
        version_token = uuid.uuid4().hex
        snapshot.update(snapshot_updates or {})
        snapshot["connector_type"] = connection.connector_type
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalConnectionVersion,
            tenant_id=connection.tenant_id,
            record_data={
                "connection_id": str(connection.id),
                "version_no": next_version_no,
                "version_token": version_token,
            },
            values={
                "connection_id": connection.id,
                "version_no": next_version_no,
                "version_token": version_token,
                "config_snapshot_json": snapshot,
                "supersedes_id": latest.id if latest else None,
                "status": status,
                "created_by": created_by,
            },
        )

    async def set_connection_status(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        new_status: str,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        connection = await self._get_connection(
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        _, runtime_state = await resolve_connection_runtime_state(
            self._session,
            connection=connection,
        )
        normalized = str(new_status or "").strip().lower()
        if normalized not in {"active", "suspended", "revoked"}:
            raise ValidationError("Unsupported connection status")
        current_status = str(runtime_state.get("connection_status") or connection.connection_status).strip().lower()
        if normalized == "active" and current_status == "revoked":
            raise ValidationError("Revoked connections cannot be re-activated")
        if current_status == normalized:
            return {
                "connection_id": str(connection.id),
                "connection_status": current_status,
                "idempotent_replay": True,
            }

        await self._append_version(
            connection=connection,
            created_by=actor_user_id,
            snapshot_updates={
                "connection_status": normalized,
                "status_transition": normalized,
            },
        )
        await self._session.flush()
        return {
            "connection_id": str(connection.id),
            "connection_status": normalized,
            "idempotent_replay": False,
        }

    async def rotate_credentials(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        credential_updates: Mapping[str, Any],
    ) -> dict[str, Any]:
        connection = await self._get_connection(
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        _, runtime_state = await resolve_connection_runtime_state(
            self._session,
            connection=connection,
        )
        updates = {
            key: value
            for key, value in dict(credential_updates or {}).items()
            if key in _ALLOWED_CREDENTIAL_KEYS and value is not None
        }
        if not updates:
            raise ValidationError("No supported credential fields supplied for rotation")

        current_secret_ref = str(
            runtime_state.get("oauth_secret_ref")
            or runtime_state.get("secret_ref")
            or connection.secret_ref
            or ""
        ).strip() or None
        new_secret_ref = await secret_store.put_secret(current_secret_ref, updates)
        await self._append_version(
            connection=connection,
            created_by=actor_user_id,
            snapshot_updates={
                "secret_ref": new_secret_ref,
                "oauth_secret_ref": new_secret_ref,
                **updates,
            },
        )
        await self._session.flush()
        return {
            "connection_id": str(connection.id),
            "rotated": True,
            "updated_fields": sorted(updates.keys()),
        }

    async def upgrade_connector_version(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        pinned_connector_version: str,
    ) -> dict[str, Any]:
        connection = await self._get_connection(
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        _, runtime_state = await resolve_connection_runtime_state(
            self._session,
            connection=connection,
        )
        version = str(pinned_connector_version or "").strip()
        if not version:
            raise ValidationError("pinned_connector_version is required")
        current_pinned_version = str(
            runtime_state.get("pinned_connector_version")
            or connection.pinned_connector_version
            or ""
        ).strip()
        if current_pinned_version == version:
            return {
                "connection_id": str(connection.id),
                "pinned_connector_version": version,
                "idempotent_replay": True,
            }

        await self._append_version(
            connection=connection,
            created_by=actor_user_id,
            snapshot_updates={"pinned_connector_version": version},
        )
        await self._session.flush()
        return {
            "connection_id": str(connection.id),
            "pinned_connector_version": version,
            "idempotent_replay": False,
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "set_status":
            return await self.set_connection_status(
                tenant_id=kwargs["tenant_id"],
                connection_id=kwargs["connection_id"],
                new_status=str(kwargs["new_status"]),
                actor_user_id=kwargs["actor_user_id"],
            )
        if action == "rotate_credentials":
            return await self.rotate_credentials(
                tenant_id=kwargs["tenant_id"],
                connection_id=kwargs["connection_id"],
                actor_user_id=kwargs["actor_user_id"],
                credential_updates=dict(kwargs.get("credential_updates", {})),
            )
        if action == "upgrade_connector_version":
            return await self.upgrade_connector_version(
                tenant_id=kwargs["tenant_id"],
                connection_id=kwargs["connection_id"],
                actor_user_id=kwargs["actor_user_id"],
                pinned_connector_version=str(kwargs["pinned_connector_version"]),
            )
        raise ValidationError("Unsupported connection service action")
