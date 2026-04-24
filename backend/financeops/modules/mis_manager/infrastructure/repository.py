from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import (
    MisDataSnapshot,
    MisDriftEvent,
    MisIngestionException,
    MisNormalizedLine,
    MisTemplate,
    MisTemplateVersion,
)
from financeops.modules.mis_manager.domain.entities import (
    NormalizedLine,
    ValidationException,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class MisManagerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_template_by_code(
        self, *, tenant_id: uuid.UUID, template_code: str
    ) -> MisTemplate | None:
        result = await self._session.execute(
            select(MisTemplate).where(
                MisTemplate.tenant_id == tenant_id,
                MisTemplate.template_code == template_code,
            )
        )
        return result.scalar_one_or_none()

    async def get_template_by_id(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> MisTemplate | None:
        result = await self._session.execute(
            select(MisTemplate).where(
                MisTemplate.tenant_id == tenant_id,
                MisTemplate.id == template_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_templates(self, *, tenant_id: uuid.UUID) -> list[MisTemplate]:
        result = await self._session.execute(
            select(MisTemplate)
            .where(MisTemplate.tenant_id == tenant_id)
            .order_by(MisTemplate.created_at.desc(), MisTemplate.id.desc())
        )
        return list(result.scalars().all())

    async def create_template(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        template_code: str,
        template_name: str,
        template_type: str,
        description: str | None,
        created_by: uuid.UUID,
    ) -> MisTemplate:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MisTemplate,
            tenant_id=tenant_id,
            record_data={
                "template_code": template_code,
                "template_name": template_name,
                "template_type": template_type,
            },
            values={
                "organisation_id": organisation_id,
                "template_code": template_code,
                "template_name": template_name,
                "template_type": template_type,
                "description": description,
                "status": "active",
                "created_by": created_by,
                # Legacy compatibility fields retained until hard cut-over.
                "name": template_name,
                "entity_name": str(organisation_id),
                "version": 1,
                "is_master": False,
                "is_active": True,
                "template_data": {"phase": "1f1"},
                "sheet_count": 0,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="mis.template.created",
                resource_type="mis_template",
                resource_name=template_code,
            ),
        )

    async def next_template_version_no(self, *, template_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(MisTemplateVersion.version_no)).where(
                MisTemplateVersion.template_id == template_id,
            )
        )
        last_no = result.scalar_one_or_none()
        return int(last_no or 0) + 1

    async def list_template_versions(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> list[MisTemplateVersion]:
        result = await self._session.execute(
            select(MisTemplateVersion)
            .where(
                MisTemplateVersion.tenant_id == tenant_id,
                MisTemplateVersion.template_id == template_id,
            )
            .order_by(MisTemplateVersion.version_no.desc(), MisTemplateVersion.id.desc())
        )
        return list(result.scalars().all())

    async def get_template_version(
        self,
        *,
        tenant_id: uuid.UUID,
        template_version_id: uuid.UUID,
    ) -> MisTemplateVersion | None:
        result = await self._session.execute(
            select(MisTemplateVersion).where(
                MisTemplateVersion.tenant_id == tenant_id,
                MisTemplateVersion.id == template_version_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_template_version(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> MisTemplateVersion | None:
        result = await self._session.execute(
            select(MisTemplateVersion)
            .where(
                MisTemplateVersion.tenant_id == tenant_id,
                MisTemplateVersion.template_id == template_id,
                MisTemplateVersion.status == "active",
            )
            .order_by(
                MisTemplateVersion.created_at.desc(),
                MisTemplateVersion.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_template_version_by_token(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        version_token: str,
    ) -> MisTemplateVersion | None:
        result = await self._session.execute(
            select(MisTemplateVersion).where(
                MisTemplateVersion.tenant_id == tenant_id,
                MisTemplateVersion.template_id == template_id,
                MisTemplateVersion.version_token == version_token,
            )
        )
        return result.scalar_one_or_none()

    async def insert_template_version(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        version_no: int,
        version_token: str,
        based_on_version_id: uuid.UUID | None,
        supersedes_id: uuid.UUID | None,
        structure_hash: str,
        header_hash: str,
        row_signature_hash: str,
        column_signature_hash: str,
        detection_summary_json: dict[str, Any],
        drift_reason: str | None,
        status: str,
        effective_from: date | None,
        created_by: uuid.UUID,
    ) -> MisTemplateVersion:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MisTemplateVersion,
            tenant_id=tenant_id,
            record_data={
                "template_id": str(template_id),
                "version_no": version_no,
                "version_token": version_token,
                "structure_hash": structure_hash,
            },
            values={
                "template_id": template_id,
                "version_no": version_no,
                "version_token": version_token,
                "based_on_version_id": based_on_version_id,
                "supersedes_id": supersedes_id,
                "structure_hash": structure_hash,
                "header_hash": header_hash,
                "row_signature_hash": row_signature_hash,
                "column_signature_hash": column_signature_hash,
                "detection_summary_json": detection_summary_json,
                "drift_reason": drift_reason,
                "status": status,
                "effective_from": effective_from,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="mis.template.version.created",
                resource_type="mis_template_version",
                resource_name=str(template_id),
            ),
        )

    async def insert_drift_event(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        prior_template_version_id: uuid.UUID,
        candidate_template_version_id: uuid.UUID,
        drift_type: str,
        drift_details_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> MisDriftEvent:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MisDriftEvent,
            tenant_id=tenant_id,
            record_data={
                "template_id": str(template_id),
                "drift_type": drift_type,
                "candidate_template_version_id": str(candidate_template_version_id),
            },
            values={
                "template_id": template_id,
                "prior_template_version_id": prior_template_version_id,
                "candidate_template_version_id": candidate_template_version_id,
                "drift_type": drift_type,
                "drift_details_json": drift_details_json,
                "decision_status": "pending_review",
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="mis.template.drift_detected",
                resource_type="mis_drift_event",
                resource_name=str(template_id),
            ),
        )

    async def get_drift_event(
        self, *, tenant_id: uuid.UUID, drift_event_id: uuid.UUID
    ) -> MisDriftEvent | None:
        result = await self._session.execute(
            select(MisDriftEvent).where(
                MisDriftEvent.tenant_id == tenant_id,
                MisDriftEvent.id == drift_event_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_snapshot_by_token(
        self,
        *,
        tenant_id: uuid.UUID,
        template_version_id: uuid.UUID,
        snapshot_token: str,
    ) -> MisDataSnapshot | None:
        result = await self._session.execute(
            select(MisDataSnapshot).where(
                MisDataSnapshot.tenant_id == tenant_id,
                MisDataSnapshot.template_version_id == template_version_id,
                MisDataSnapshot.snapshot_token == snapshot_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_snapshot(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> MisDataSnapshot | None:
        result = await self._session.execute(
            select(MisDataSnapshot).where(
                MisDataSnapshot.tenant_id == tenant_id,
                MisDataSnapshot.id == snapshot_id,
            )
        )
        return result.scalar_one_or_none()

    async def insert_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        template_id: uuid.UUID,
        template_version_id: uuid.UUID,
        reporting_period: date,
        upload_artifact_id: uuid.UUID,
        snapshot_token: str,
        source_file_hash: str,
        sheet_name: str,
        snapshot_status: str,
        validation_summary_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> MisDataSnapshot:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=MisDataSnapshot,
            tenant_id=tenant_id,
            record_data={
                "template_version_id": str(template_version_id),
                "snapshot_token": snapshot_token,
                "reporting_period": reporting_period.isoformat(),
                "snapshot_status": snapshot_status,
            },
            values={
                "organisation_id": organisation_id,
                "template_id": template_id,
                "template_version_id": template_version_id,
                "reporting_period": reporting_period,
                "upload_artifact_id": upload_artifact_id,
                "snapshot_token": snapshot_token,
                "source_file_hash": source_file_hash,
                "sheet_name": sheet_name,
                "snapshot_status": snapshot_status,
                "validation_summary_json": validation_summary_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="mis.snapshot.created",
                resource_type="mis_snapshot",
                resource_name=str(template_version_id),
            ),
        )

    async def insert_normalized_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        created_by: uuid.UUID,
        lines: Iterable[NormalizedLine],
    ) -> list[MisNormalizedLine]:
        rows: list[MisNormalizedLine] = []
        for line in lines:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=MisNormalizedLine,
                tenant_id=tenant_id,
                record_data={
                    "snapshot_id": str(snapshot_id),
                    "line_no": line.line_no,
                    "canonical_metric_code": line.canonical_metric_code,
                    "period_value": str(line.period_value),
                },
                values={
                    "snapshot_id": snapshot_id,
                    "line_no": line.line_no,
                    "canonical_metric_code": line.canonical_metric_code,
                    "canonical_dimension_json": line.canonical_dimension_json,
                    "source_row_ref": line.source_row_ref,
                    "source_column_ref": line.source_column_ref,
                    "period_value": line.period_value,
                    "currency_code": line.currency_code,
                    "sign_applied": line.sign_applied,
                    "validation_status": line.validation_status.value,
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_normalized_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> list[MisNormalizedLine]:
        result = await self._session.execute(
            select(MisNormalizedLine)
            .where(
                MisNormalizedLine.tenant_id == tenant_id,
                MisNormalizedLine.snapshot_id == snapshot_id,
            )
            .order_by(MisNormalizedLine.line_no.asc())
        )
        return list(result.scalars().all())

    async def insert_exceptions(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        created_by: uuid.UUID,
        exceptions: Iterable[ValidationException],
    ) -> list[MisIngestionException]:
        rows: list[MisIngestionException] = []
        for item in exceptions:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=MisIngestionException,
                tenant_id=tenant_id,
                record_data={
                    "snapshot_id": str(snapshot_id),
                    "exception_code": item.exception_code,
                    "severity": item.severity,
                },
                values={
                    "snapshot_id": snapshot_id,
                    "exception_code": item.exception_code,
                    "severity": item.severity,
                    "source_ref": item.source_ref,
                    "message": item.message,
                    "resolution_status": "open",
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_exceptions(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> list[MisIngestionException]:
        result = await self._session.execute(
            select(MisIngestionException)
            .where(
                MisIngestionException.tenant_id == tenant_id,
                MisIngestionException.snapshot_id == snapshot_id,
            )
            .order_by(MisIngestionException.created_at.asc(), MisIngestionException.id.asc())
        )
        return list(result.scalars().all())

    async def get_latest_snapshot_for_period(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID | None,
        reporting_period: date,
    ) -> MisDataSnapshot | None:
        stmt = (
            select(MisDataSnapshot)
            .where(
                MisDataSnapshot.tenant_id == tenant_id,
                MisDataSnapshot.reporting_period == reporting_period,
            )
            .order_by(MisDataSnapshot.created_at.desc(), MisDataSnapshot.id.desc())
            .limit(1)
        )
        if entity_id is not None:
            stmt = stmt.where(MisDataSnapshot.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_snapshots_for_entity(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID | None = None,
    ) -> list[MisDataSnapshot]:
        stmt = (
            select(MisDataSnapshot)
            .where(MisDataSnapshot.tenant_id == tenant_id)
            .order_by(MisDataSnapshot.reporting_period.desc(), MisDataSnapshot.created_at.desc())
        )
        if entity_id is not None:
            stmt = stmt.where(MisDataSnapshot.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def summarize_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> dict[str, Any]:
        lines = await self.list_normalized_lines(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )
        exceptions = await self.list_exceptions(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )
        total = sum([line.period_value for line in lines], start=0)
        return {
            "line_count": len(lines),
            "exception_count": len(exceptions),
            "total_period_value": str(total),
        }
