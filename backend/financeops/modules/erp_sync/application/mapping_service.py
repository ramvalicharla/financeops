from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.erp_sync import (
    ExternalConnection,
    ExternalMappingDefinition,
    ExternalMappingVersion,
)
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.tokens import build_version_rows_token


class MappingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_mapping_definition(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        mapping_code: str,
        mapping_name: str,
        dataset_type: str,
        created_by: uuid.UUID,
        status: str = "draft",
    ) -> ExternalMappingDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalMappingDefinition,
            tenant_id=tenant_id,
            record_data={
                "organisation_id": str(organisation_id),
                "mapping_code": mapping_code,
                "dataset_type": dataset_type,
            },
            values={
                "organisation_id": organisation_id,
                "mapping_code": mapping_code,
                "mapping_name": mapping_name,
                "dataset_type": dataset_type,
                "mapping_status": status,
                "created_by": created_by,
            },
        )

    async def create_mapping_version(
        self,
        *,
        tenant_id: uuid.UUID,
        mapping_definition_id: uuid.UUID,
        mapping_payload_json: Mapping[str, Any],
        created_by: uuid.UUID,
        activate: bool = False,
        supersedes_id: uuid.UUID | None = None,
    ) -> ExternalMappingVersion:
        definition = (
            await self._session.execute(
                select(ExternalMappingDefinition).where(
                    ExternalMappingDefinition.id == mapping_definition_id,
                    ExternalMappingDefinition.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("Mapping definition not found")

        max_version = (
            await self._session.execute(
                select(func.max(ExternalMappingVersion.version_no)).where(
                    ExternalMappingVersion.mapping_definition_id == mapping_definition_id,
                    ExternalMappingVersion.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        next_version = int(max_version or 0) + 1

        if activate:
            active_exists = (
                await self._session.execute(
                    select(ExternalMappingVersion.id).where(
                        ExternalMappingVersion.mapping_definition_id == mapping_definition_id,
                        ExternalMappingVersion.tenant_id == tenant_id,
                        ExternalMappingVersion.status == "active",
                    )
                )
            ).scalar_one_or_none()
            if active_exists is not None:
                raise ValidationError("Active mapping version already exists for this mapping definition")

        version_token = build_version_rows_token([dict(mapping_payload_json)])
        status = "active" if activate else "candidate"

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalMappingVersion,
            tenant_id=tenant_id,
            record_data={
                "mapping_definition_id": str(mapping_definition_id),
                "version_no": next_version,
                "version_token": version_token,
            },
            values={
                "mapping_definition_id": mapping_definition_id,
                "version_no": next_version,
                "version_token": version_token,
                "mapping_payload_json": dict(mapping_payload_json),
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
        )

    async def get_active_mapping_for_connection(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        dataset_type: str,
    ) -> dict[str, Any]:
        connection = (
            await self._session.execute(
                select(ExternalConnection).where(
                    ExternalConnection.id == connection_id,
                    ExternalConnection.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if connection is None:
            raise NotFoundError("Connection not found")

        definition = (
            await self._session.execute(
                select(ExternalMappingDefinition)
                .where(
                    ExternalMappingDefinition.tenant_id == tenant_id,
                    ExternalMappingDefinition.organisation_id == connection.organisation_id,
                    ExternalMappingDefinition.dataset_type == dataset_type,
                    ExternalMappingDefinition.mapping_status == "active",
                )
                .order_by(ExternalMappingDefinition.created_at.desc(), ExternalMappingDefinition.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("No active mapping definition for dataset and organisation")

        version = (
            await self._session.execute(
                select(ExternalMappingVersion)
                .where(
                    ExternalMappingVersion.tenant_id == tenant_id,
                    ExternalMappingVersion.mapping_definition_id == definition.id,
                    ExternalMappingVersion.status == "active",
                )
                .order_by(ExternalMappingVersion.version_no.desc(), ExternalMappingVersion.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("No active mapping version for mapping definition")

        return {
            "mapping_definition_id": str(definition.id),
            "mapping_code": definition.mapping_code,
            "mapping_version_id": str(version.id),
            "mapping_version_no": version.version_no,
            "mapping_version_token": version.version_token,
            "mapping_payload_json": dict(version.mapping_payload_json or {}),
            "resolved_at": datetime.now(UTC).isoformat(),
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "resolve_active":
            return await self.get_active_mapping_for_connection(
                tenant_id=kwargs["tenant_id"],
                connection_id=kwargs["connection_id"],
                dataset_type=str(kwargs["dataset_type"]),
            )
        if action == "create_definition":
            row = await self.create_mapping_definition(
                tenant_id=kwargs["tenant_id"],
                organisation_id=kwargs["organisation_id"],
                mapping_code=str(kwargs["mapping_code"]),
                mapping_name=str(kwargs["mapping_name"]),
                dataset_type=str(kwargs["dataset_type"]),
                created_by=kwargs["created_by"],
                status=str(kwargs.get("status", "draft")),
            )
            return {"mapping_definition_id": str(row.id)}
        if action == "create_version":
            row = await self.create_mapping_version(
                tenant_id=kwargs["tenant_id"],
                mapping_definition_id=kwargs["mapping_definition_id"],
                mapping_payload_json=kwargs.get("mapping_payload_json", {}),
                created_by=kwargs["created_by"],
                activate=bool(kwargs.get("activate", False)),
                supersedes_id=kwargs.get("supersedes_id"),
            )
            return {"mapping_version_id": str(row.id), "version_token": row.version_token}
        raise ValidationError("Unsupported mapping service action")
