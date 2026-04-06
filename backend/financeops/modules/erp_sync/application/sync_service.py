from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import FinanceOpsError, NotFoundError, ValidationError
from financeops.db.models.erp_sync import (
    ExternalConnection,
    ExternalConnectionVersion,
    ExternalRawSnapshot,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
    ExternalSyncRun,
)
from financeops.modules.erp_sync.application.connection_service import (
    get_latest_connection_version,
    merge_connection_runtime_snapshot,
)
from financeops.modules.erp_sync.application.mapping_service import MappingService
from financeops.modules.erp_sync.application.normalization_service import NormalizationService
from financeops.modules.erp_sync.application.period_service import PeriodService
from financeops.modules.erp_sync.application.validation_service import ValidationService
from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType, SyncRunStatus
from financeops.modules.erp_sync.domain.schemas import SyncTokenPayload
from financeops.modules.erp_sync.infrastructure.connectors.registry import get_connector
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.tokens import build_token
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


NORMALIZATION_VERSION = "phase4c.v1"


class DuplicateSyncError(FinanceOpsError):
    status_code = 409
    error_code = "DUPLICATE_SYNC"


class SyncService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        mapping_service: MappingService | None = None,
        period_service: PeriodService | None = None,
        normalization_service: NormalizationService | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self._session = session
        self._mapping_service = mapping_service or MappingService(session)
        self._period_service = period_service or PeriodService()
        self._normalization_service = normalization_service or NormalizationService()
        self._validation_service = validation_service or ValidationService()

    async def trigger_sync_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        entity_id: uuid.UUID | None,
        connection_id: uuid.UUID,
        sync_definition_id: uuid.UUID,
        sync_definition_version_id: uuid.UUID,
        dataset_type: DatasetType,
        idempotency_key: str,
        created_by: uuid.UUID,
        extraction_kwargs: Mapping[str, Any] | None = None,
        resumed_from_run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        connection, definition, version = await self._fetch_sync_context(
            tenant_id=tenant_id,
            connection_id=connection_id,
            sync_definition_id=sync_definition_id,
            sync_definition_version_id=sync_definition_version_id,
        )
        if definition.dataset_type != dataset_type.value:
            raise ValidationError("Dataset type does not match sync definition")

        connector = get_connector(ConnectorType(connection.connector_type))
        extraction_input = dict(extraction_kwargs or {})
        resolved_secret_ref = await self._resolve_active_secret_ref(
            tenant_id=tenant_id,
            connection=connection,
        )
        connection_runtime = await self._resolve_connection_runtime_state(
            tenant_id=tenant_id,
            connection=connection,
        )
        if resolved_secret_ref and not extraction_input.get("credentials"):
            extraction_input.setdefault("secret_ref", resolved_secret_ref)
        extracted = await connector.extract(dataset_type, **extraction_input)
        raw_snapshot_payload_hash = sha256_hex_text(canonical_json_dumps(self._json_safe(extracted)))

        mapping_resolution = await self._mapping_service.get_active_mapping_for_connection(
            tenant_id=tenant_id,
            connection_id=connection_id,
            dataset_type=dataset_type.value,
        )
        period_resolution_hash = sha256_hex_text(canonical_json_dumps(version.period_resolution_json))
        extraction_scope_hash = sha256_hex_text(canonical_json_dumps(version.extraction_scope_json))
        sync_token = await self._build_sync_token(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            entity_id=entity_id,
            dataset_type=dataset_type,
            connector_type=ConnectorType(connection.connector_type),
            connector_version=str(
                connection_runtime.get("pinned_connector_version")
                or connection.pinned_connector_version
                or connector.connector_version
            ),
            source_system_instance_id=connection.source_system_instance_id,
            sync_definition_id=sync_definition_id,
            sync_definition_version=version.version_no,
            period_resolution_hash=period_resolution_hash,
            extraction_scope_hash=extraction_scope_hash,
            raw_snapshot_payload_hash=raw_snapshot_payload_hash,
            mapping_version_token=str(mapping_resolution["mapping_version_token"]),
            normalization_version=NORMALIZATION_VERSION,
            pii_masking_enabled=bool(connection.pii_masking_enabled),
            data_residency_region=connection.data_residency_region,
        )

        duplicate = (
            await self._session.execute(
                select(ExternalSyncRun.id).where(
                    ExternalSyncRun.tenant_id == tenant_id,
                    ExternalSyncRun.run_token == sync_token,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise DuplicateSyncError("Duplicate sync token detected; run rejected")

        normalized_payload = self._normalization_service.normalize(
            dataset_type=dataset_type,
            raw_payload=extracted,
            entity_id=str(entity_id or definition.entity_id or organisation_id),
            currency=str(extracted.get("currency", "INR")),
        )
        validation_summary = self._validation_service.validate(
            dataset_type=dataset_type.value,
            canonical_payload=normalized_payload,
            raw_payload=extracted,
            context={
                "entity_id": str(entity_id or definition.entity_id or ""),
                "capability_supported": True,
                "mapping_complete": True,
                "duplicate_sync_token": False,
                "raw_snapshot_payload_hash": raw_snapshot_payload_hash,
                "expected_raw_snapshot_hash": raw_snapshot_payload_hash,
            },
        )
        run_status = (
            SyncRunStatus.HALTED.value
            if validation_summary["run_status"] == SyncRunStatus.HALTED.value
            else SyncRunStatus.COMPLETED.value
        )

        run_row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalSyncRun,
            tenant_id=tenant_id,
            record_data={
                "connection_id": str(connection_id),
                "sync_definition_id": str(sync_definition_id),
                "run_token": sync_token,
                "dataset_type": dataset_type.value,
            },
            values={
                "organisation_id": organisation_id,
                "entity_id": entity_id,
                "connection_id": connection_id,
                "sync_definition_id": sync_definition_id,
                "sync_definition_version_id": sync_definition_version_id,
                "dataset_type": dataset_type.value,
                "reporting_period_label": self._resolve_reporting_period_label(version.period_resolution_json),
                "run_token": sync_token,
                "idempotency_key": idempotency_key,
                "run_status": run_status,
                "raw_snapshot_payload_hash": raw_snapshot_payload_hash,
                "mapping_version_token": str(mapping_resolution["mapping_version_token"]),
                "normalization_version": NORMALIZATION_VERSION,
                "validation_summary_json": validation_summary,
                "extraction_total_records": int(extracted.get("line_count") or 0),
                "extraction_fetched_records": int(extracted.get("line_count") or 0),
                "extraction_checkpoint": extracted.get("next_checkpoint"),
                "extraction_chunk_size": int(extracted.get("chunk_size") or 500),
                "is_resumable": bool(extracted.get("is_resumable", connector.supports_resumable_extraction)),
                "resumed_from_run_id": resumed_from_run_id,
                "published_at": None,
                "created_by": created_by,
            },
        )

        raw_snapshot = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalRawSnapshot,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(run_row.id),
                "payload_hash": raw_snapshot_payload_hash,
                "storage_ref": f"erp_sync/raw/{run_row.id}.json",
            },
            values={
                "sync_run_id": run_row.id,
                "snapshot_token": build_token(
                    {
                        "tenant_id": str(tenant_id),
                        "sync_run_id": str(run_row.id),
                        "payload_hash": raw_snapshot_payload_hash,
                        "frozen": False,
                    }
                ),
                "storage_ref": f"erp_sync/raw/{run_row.id}.json",
                "payload_hash": raw_snapshot_payload_hash,
                "payload_size_bytes": len(canonical_json_dumps(self._json_safe(extracted)).encode("utf-8")),
                "frozen": False,
                "created_by": created_by,
            },
        )
        return {
            "sync_run_id": str(run_row.id),
            "sync_run_status": run_row.run_status,
            "sync_token": run_row.run_token,
            "raw_snapshot_id": str(raw_snapshot.id),
            "raw_snapshot_token": raw_snapshot.snapshot_token,
            "validation_summary": validation_summary,
        }

    async def freeze_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        source_snapshot = (
            await self._session.execute(
                select(ExternalRawSnapshot)
                .where(
                    ExternalRawSnapshot.tenant_id == tenant_id,
                    ExternalRawSnapshot.sync_run_id == sync_run_id,
                )
                .order_by(ExternalRawSnapshot.created_at.desc(), ExternalRawSnapshot.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if source_snapshot is None:
            raise NotFoundError("Raw snapshot not found for sync run")
        if source_snapshot.frozen:
            return {
                "snapshot_id": str(source_snapshot.id),
                "snapshot_token": source_snapshot.snapshot_token,
                "frozen": True,
            }

        frozen_token = build_token(
            {
                "tenant_id": str(tenant_id),
                "sync_run_id": str(sync_run_id),
                "payload_hash": source_snapshot.payload_hash,
                "frozen": True,
                "source_snapshot_token": source_snapshot.snapshot_token,
            }
        )
        frozen_snapshot = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalRawSnapshot,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(sync_run_id),
                "payload_hash": source_snapshot.payload_hash,
                "storage_ref": source_snapshot.storage_ref,
                "frozen": True,
            },
            values={
                "sync_run_id": sync_run_id,
                "snapshot_token": frozen_token,
                "storage_ref": source_snapshot.storage_ref,
                "payload_hash": source_snapshot.payload_hash,
                "payload_size_bytes": int(source_snapshot.payload_size_bytes),
                "frozen": True,
                "created_by": created_by,
            },
        )
        return {
            "snapshot_id": str(frozen_snapshot.id),
            "snapshot_token": frozen_snapshot.snapshot_token,
            "frozen": True,
        }

    async def resume_sync_run(
        self,
        *,
        tenant_id: uuid.UUID,
        paused_run_id: uuid.UUID,
        idempotency_key: str,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        paused_run = (
            await self._session.execute(
                select(ExternalSyncRun).where(
                    ExternalSyncRun.id == paused_run_id,
                    ExternalSyncRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if paused_run is None:
            raise NotFoundError("Paused sync run not found")
        if paused_run.run_status != SyncRunStatus.PAUSED.value:
            raise ValidationError("Only PAUSED runs can be resumed")

        extraction_kwargs = {
            "checkpoint": paused_run.extraction_checkpoint or {},
        }
        resumed = await self.trigger_sync_run(
            tenant_id=tenant_id,
            organisation_id=paused_run.organisation_id,
            entity_id=paused_run.entity_id,
            connection_id=paused_run.connection_id,
            sync_definition_id=paused_run.sync_definition_id,
            sync_definition_version_id=paused_run.sync_definition_version_id,
            dataset_type=DatasetType(paused_run.dataset_type),
            idempotency_key=idempotency_key,
            created_by=created_by,
            extraction_kwargs=extraction_kwargs,
            resumed_from_run_id=paused_run.id,
        )
        return {
            "sync_run_id": resumed["sync_run_id"],
            "sync_run_status": resumed["sync_run_status"],
            "resumed_from_run_id": str(paused_run.id),
        }

    async def _fetch_sync_context(
        self,
        *,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
        sync_definition_id: uuid.UUID,
        sync_definition_version_id: uuid.UUID,
    ) -> tuple[ExternalConnection, ExternalSyncDefinition, ExternalSyncDefinitionVersion]:
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
                select(ExternalSyncDefinition).where(
                    ExternalSyncDefinition.id == sync_definition_id,
                    ExternalSyncDefinition.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if definition is None:
            raise NotFoundError("Sync definition not found")

        version = (
            await self._session.execute(
                select(ExternalSyncDefinitionVersion).where(
                    ExternalSyncDefinitionVersion.id == sync_definition_version_id,
                    ExternalSyncDefinitionVersion.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("Sync definition version not found")
        return connection, definition, version

    async def _resolve_active_secret_ref(
        self,
        *,
        tenant_id: uuid.UUID,
        connection: ExternalConnection,
    ) -> str | None:
        latest_version = (
            await get_latest_connection_version(
                self._session,
                tenant_id=tenant_id,
                connection_id=connection.id,
            )
        )
        snapshot = merge_connection_runtime_snapshot(connection, latest_version)
        resolved_secret_ref = str(
            snapshot.get("oauth_secret_ref")
            or snapshot.get("secret_ref")
            or connection.secret_ref
            or ""
        ).strip()
        return resolved_secret_ref or None

    async def _resolve_connection_runtime_state(
        self,
        *,
        tenant_id: uuid.UUID,
        connection: ExternalConnection,
    ) -> dict[str, Any]:
        latest_version = await get_latest_connection_version(
            self._session,
            tenant_id=tenant_id,
            connection_id=connection.id,
        )
        return merge_connection_runtime_snapshot(connection, latest_version)

    async def _build_sync_token(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        entity_id: uuid.UUID | None,
        dataset_type: DatasetType,
        connector_type: ConnectorType,
        connector_version: str,
        source_system_instance_id: str,
        sync_definition_id: uuid.UUID,
        sync_definition_version: int,
        period_resolution_hash: str,
        extraction_scope_hash: str,
        raw_snapshot_payload_hash: str,
        mapping_version_token: str,
        normalization_version: str,
        pii_masking_enabled: bool,
        data_residency_region: str,
    ) -> str:
        payload = SyncTokenPayload(
            tenant_id=str(tenant_id),
            organisation_id=str(organisation_id),
            entity_id=str(entity_id or ""),
            dataset_type=dataset_type,
            connector_type=connector_type,
            connector_version=connector_version,
            source_system_instance_id=source_system_instance_id,
            sync_definition_id=str(sync_definition_id),
            sync_definition_version=sync_definition_version,
            period_resolution_hash=period_resolution_hash,
            extraction_scope_hash=extraction_scope_hash,
            raw_snapshot_payload_hash=raw_snapshot_payload_hash,
            mapping_version_token=mapping_version_token,
            normalization_version=normalization_version,
            pii_masking_enabled=pii_masking_enabled,
            data_residency_region=data_residency_region,
        )
        return build_token(payload.model_dump(mode="python"))

    @staticmethod
    def _resolve_reporting_period_label(period_resolution_json: Mapping[str, Any]) -> str | None:
        granularity = str(period_resolution_json.get("granularity", "")).strip()
        if not granularity:
            return None
        if granularity == "as_at":
            as_at = period_resolution_json.get("as_at_date")
            return f"AS_AT:{as_at}" if as_at else "AS_AT"
        start = period_resolution_json.get("period_start")
        end = period_resolution_json.get("period_end")
        if start and end:
            return f"{start}:{end}"
        return granularity

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): SyncService._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [SyncService._json_safe(v) for v in value]
        if isinstance(value, (datetime, uuid.UUID, DatasetType, ConnectorType)):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        return value

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "trigger":
            return await self.trigger_sync_run(
                tenant_id=kwargs["tenant_id"],
                organisation_id=kwargs["organisation_id"],
                entity_id=kwargs.get("entity_id"),
                connection_id=kwargs["connection_id"],
                sync_definition_id=kwargs["sync_definition_id"],
                sync_definition_version_id=kwargs["sync_definition_version_id"],
                dataset_type=kwargs["dataset_type"],
                idempotency_key=str(kwargs["idempotency_key"]),
                created_by=kwargs["created_by"],
                extraction_kwargs=kwargs.get("extraction_kwargs"),
                resumed_from_run_id=kwargs.get("resumed_from_run_id"),
            )
        if action == "freeze_snapshot":
            return await self.freeze_snapshot(
                tenant_id=kwargs["tenant_id"],
                sync_run_id=kwargs["sync_run_id"],
                created_by=kwargs["created_by"],
            )
        if action == "resume":
            return await self.resume_sync_run(
                tenant_id=kwargs["tenant_id"],
                paused_run_id=kwargs["paused_run_id"],
                idempotency_key=str(kwargs["idempotency_key"]),
                created_by=kwargs["created_by"],
            )
        raise ValidationError("Unsupported sync service action")
