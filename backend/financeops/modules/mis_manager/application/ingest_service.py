from __future__ import annotations

import base64
import uuid
from datetime import date
from typing import Any

from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.application.template_detection_service import (
    TemplateDetectionService,
)
from financeops.modules.mis_manager.application.validation_service import (
    ValidationService,
)
from financeops.modules.mis_manager.domain.entities import (
    NormalizedLine,
    SheetProfile,
    ValidationException,
)
from financeops.modules.mis_manager.domain.enums import SnapshotStatus, ValidationStatus
from financeops.modules.mis_manager.domain.value_objects import (
    SnapshotTokenInput,
    VersionTokenInput,
)
from financeops.modules.mis_manager.infrastructure.file_parser_csv import (
    parse_csv_bytes,
)
from financeops.modules.mis_manager.infrastructure.file_parser_excel import (
    parse_excel_bytes,
)
from financeops.modules.mis_manager.infrastructure.repository import (
    MisManagerRepository,
)
from financeops.modules.mis_manager.infrastructure.token_builder import (
    build_version_token,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_bytes


class MisIngestService:
    def __init__(
        self,
        *,
        repository: MisManagerRepository,
        template_detection_service: TemplateDetectionService,
        mapping_service: MappingService,
        snapshot_service: SnapshotService,
        validation_service: ValidationService,
    ) -> None:
        self._repository = repository
        self._template_detection = template_detection_service
        self._mapping_service = mapping_service
        self._snapshot_service = snapshot_service
        self._validation_service = validation_service

    async def detect_template(
        self,
        *,
        tenant_id: uuid.UUID,
        template_code: str,
        file_name: str,
        file_content_base64: str,
        sheet_name: str | None,
    ) -> dict[str, Any]:
        parsed = self._parse_file(
            file_name=file_name,
            file_content_base64=file_content_base64,
            sheet_name=sheet_name,
        )
        template = await self._repository.get_template_by_code(
            tenant_id=tenant_id, template_code=template_code
        )
        prior_version = None
        if template is not None:
            prior_version = await self._repository.get_active_template_version(
                tenant_id=tenant_id,
                template_id=template.id,
            )

        profile = SheetProfile(
            sheet_name=str(parsed["sheet_name"]),
            header_row_index=int(parsed["header_row_index"]),
            data_start_row_index=int(parsed["data_start_row_index"]),
            headers=list(parsed["headers"]),
            row_labels=list(parsed["row_labels"]),
            column_order=list(parsed["column_order"]),
            section_breaks=list(parsed["section_breaks"]),
            blank_row_density=parsed["blank_row_density"],
            formula_density=parsed["formula_density"],
            text_to_numeric_ratio=parsed["text_to_numeric_ratio"],
            merged_cell_count=int(parsed["merged_cell_count"]),
        )
        detection, drift = self._template_detection.detect(
            profile=profile,
            prior_template_version_id=(
                prior_version.id if prior_version is not None else None
            ),
            prior_header_hash=(
                prior_version.header_hash if prior_version is not None else None
            ),
            prior_row_signature_hash=(
                prior_version.row_signature_hash if prior_version is not None else None
            ),
            prior_column_signature_hash=(
                prior_version.column_signature_hash
                if prior_version is not None
                else None
            ),
            prior_structure_hash=(
                prior_version.structure_hash if prior_version is not None else None
            ),
        )

        mappings = self._mapping_service.map_columns(profile.headers)
        row_mappings = self._mapping_service.map_rows_to_canonical_metrics(
            profile.row_labels
        )

        return {
            "template_id": str(template.id) if template else None,
            "template_match_outcome": detection.template_match_outcome,
            "prior_template_version_id": (
                str(detection.prior_template_version_id)
                if detection.prior_template_version_id
                else None
            ),
            "signature": {
                "structure_hash": detection.signature.structure_hash,
                "header_hash": detection.signature.header_hash,
                "row_signature_hash": detection.signature.row_signature_hash,
                "column_signature_hash": detection.signature.column_signature_hash,
                "section_signature_hash": detection.signature.section_signature_hash,
            },
            "detection_summary_json": detection.detection_summary,
            "drift": drift,
            "mapped_columns": mappings,
            "mapped_rows": [
                {
                    "source_label": item.source_label,
                    "normalized_label": item.normalized_label,
                    "canonical_metric_code": item.canonical_metric_code,
                    "confidence_score": str(item.confidence_score),
                }
                for item in row_mappings
            ],
        }

    async def commit_template_version(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        template_code: str,
        template_name: str,
        template_type: str,
        created_by: uuid.UUID,
        structure_hash: str,
        header_hash: str,
        row_signature_hash: str,
        column_signature_hash: str,
        detection_summary_json: dict[str, Any],
        drift_reason: str | None,
        activate: bool,
        effective_from: date | None,
    ) -> dict[str, Any]:
        template = await self._repository.get_template_by_code(
            tenant_id=tenant_id, template_code=template_code
        )
        if template is None:
            template = await self._repository.create_template(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                template_code=template_code,
                template_name=template_name,
                template_type=template_type,
                description=None,
                created_by=created_by,
            )

        version_token = build_version_token(
            VersionTokenInput(
                template_id=template.id,
                structure_hash=structure_hash,
                header_hash=header_hash,
                row_signature_hash=row_signature_hash,
                column_signature_hash=column_signature_hash,
                detection_summary_json=detection_summary_json,
            )
        )

        existing = await self._repository.get_template_version_by_token(
            tenant_id=tenant_id,
            template_id=template.id,
            version_token=version_token,
        )
        if existing is not None:
            return {
                "template_id": str(template.id),
                "template_version_id": str(existing.id),
                "version_no": existing.version_no,
                "version_token": existing.version_token,
                "status": existing.status,
                "idempotent": True,
            }

        active = await self._repository.get_active_template_version(
            tenant_id=tenant_id,
            template_id=template.id,
        )
        status = "active" if activate and active is None else "candidate"

        next_version_no = await self._repository.next_template_version_no(
            template_id=template.id
        )
        row = await self._repository.insert_template_version(
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=next_version_no,
            version_token=version_token,
            based_on_version_id=(active.id if active is not None else None),
            supersedes_id=(
                active.id if active is not None and status == "active" else None
            ),
            structure_hash=structure_hash,
            header_hash=header_hash,
            row_signature_hash=row_signature_hash,
            column_signature_hash=column_signature_hash,
            detection_summary_json=detection_summary_json,
            drift_reason=drift_reason,
            status=status,
            effective_from=effective_from,
            created_by=created_by,
        )

        drift_event_id: str | None = None
        if active is not None and active.structure_hash != structure_hash:
            drift = await self._repository.insert_drift_event(
                tenant_id=tenant_id,
                template_id=template.id,
                prior_template_version_id=active.id,
                candidate_template_version_id=row.id,
                drift_type="MAJOR_LAYOUT_CHANGE",
                drift_details_json={
                    "prior_structure_hash": active.structure_hash,
                    "candidate_structure_hash": structure_hash,
                },
                created_by=created_by,
            )
            drift_event_id = str(drift.id)

        return {
            "template_id": str(template.id),
            "template_version_id": str(row.id),
            "version_no": row.version_no,
            "version_token": row.version_token,
            "status": row.status,
            "drift_event_id": drift_event_id,
            "idempotent": False,
        }

    async def upload_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        template_id: uuid.UUID,
        template_version_id: uuid.UUID,
        reporting_period: date,
        upload_artifact_id: uuid.UUID,
        file_name: str,
        file_content_base64: str,
        sheet_name: str | None,
        currency_code: str,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        template = await self._repository.get_template_by_id(
            tenant_id=tenant_id, template_id=template_id
        )
        if template is None:
            raise ValueError("Template not found")

        template_version = await self._repository.get_template_version(
            tenant_id=tenant_id,
            template_version_id=template_version_id,
        )
        if template_version is None:
            raise ValueError("Template version not found")

        content = base64.b64decode(file_content_base64)
        source_file_hash = sha256_hex_bytes(content)
        parsed = self._parse_file(
            file_name=file_name,
            file_content_base64=file_content_base64,
            sheet_name=sheet_name,
        )
        normalization = self._snapshot_service.normalize_sheet(
            sheet_name=str(parsed["sheet_name"]),
            headers=list(parsed["headers"]),
            rows=list(parsed["rows"]),
            currency_code=currency_code,
        )

        mapping_identity = sha256_hex_bytes(
            canonical_json_dumps(parsed["headers"]).encode("utf-8")
        )
        snapshot_token = self._snapshot_service.build_snapshot_token(
            SnapshotTokenInput(
                source_file_hash=source_file_hash,
                sheet_name=str(parsed["sheet_name"]),
                structure_hash=template_version.structure_hash,
                mapping_set_identity=mapping_identity,
                validation_rule_set_identity="mis_validation_v1",
                reporting_period=reporting_period,
                template_version_id=template_version_id,
                status=SnapshotStatus.PENDING.value,
            )
        )

        existing = await self._repository.get_snapshot_by_token(
            tenant_id=tenant_id,
            template_version_id=template_version_id,
            snapshot_token=snapshot_token,
        )
        if existing is not None:
            return {
                "snapshot_id": str(existing.id),
                "snapshot_token": existing.snapshot_token,
                "snapshot_status": existing.snapshot_status,
                "idempotent": True,
            }

        validation_exceptions, validation_summary = (
            self._validation_service.validate_snapshot(
                template_type=template.template_type,
                headers=list(parsed["headers"]),
                lines=normalization.normalized_lines,
                currency_codes=[currency_code],
            )
        )
        all_exceptions = [*normalization.exceptions, *validation_exceptions]

        snapshot = await self._repository.insert_snapshot(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            template_id=template_id,
            template_version_id=template_version_id,
            reporting_period=reporting_period,
            upload_artifact_id=upload_artifact_id,
            snapshot_token=snapshot_token,
            source_file_hash=source_file_hash,
            sheet_name=str(parsed["sheet_name"]),
            snapshot_status=SnapshotStatus.PENDING.value,
            validation_summary_json=validation_summary,
            created_by=created_by,
        )
        await self._repository.insert_normalized_lines(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
            created_by=created_by,
            lines=normalization.normalized_lines,
        )
        if all_exceptions:
            await self._repository.insert_exceptions(
                tenant_id=tenant_id,
                snapshot_id=snapshot.id,
                created_by=created_by,
                exceptions=all_exceptions,
            )

        return {
            "snapshot_id": str(snapshot.id),
            "snapshot_token": snapshot.snapshot_token,
            "snapshot_status": snapshot.snapshot_status,
            "line_count": len(normalization.normalized_lines),
            "exception_count": len(all_exceptions),
            "idempotent": False,
        }

    async def validate_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        snapshot = await self._repository.get_snapshot(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )
        if snapshot is None:
            raise ValueError("Snapshot not found")

        template = await self._repository.get_template_by_id(
            tenant_id=tenant_id, template_id=snapshot.template_id
        )
        if template is None:
            raise ValueError("Template not found")

        template_version = await self._repository.get_template_version(
            tenant_id=tenant_id,
            template_version_id=snapshot.template_version_id,
        )
        if template_version is None:
            raise ValueError("Template version not found")

        existing_lines = await self._repository.list_normalized_lines(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
        )
        normalized_lines = [
            NormalizedLine(
                line_no=row.line_no,
                canonical_metric_code=row.canonical_metric_code,
                canonical_dimension_json=row.canonical_dimension_json,
                source_row_ref=row.source_row_ref,
                source_column_ref=row.source_column_ref,
                period_value=row.period_value,
                currency_code=row.currency_code,
                sign_applied=row.sign_applied,
                validation_status=ValidationStatus(row.validation_status),
            )
            for row in existing_lines
        ]

        new_exceptions, summary = self._validation_service.validate_snapshot(
            template_type=template.template_type,
            headers=[],
            lines=normalized_lines,
            currency_codes=[line.currency_code for line in normalized_lines],
        )
        target_status = (
            SnapshotStatus.FAILED.value
            if summary["status"] == "failed"
            else SnapshotStatus.VALIDATED.value
        )

        next_token = self._snapshot_service.build_snapshot_token(
            SnapshotTokenInput(
                source_file_hash=snapshot.source_file_hash,
                sheet_name=snapshot.sheet_name,
                structure_hash=template_version.structure_hash,
                mapping_set_identity="derived",
                validation_rule_set_identity="mis_validation_v1",
                reporting_period=snapshot.reporting_period,
                template_version_id=snapshot.template_version_id,
                status=target_status,
            )
        )
        existing = await self._repository.get_snapshot_by_token(
            tenant_id=tenant_id,
            template_version_id=snapshot.template_version_id,
            snapshot_token=next_token,
        )
        if existing is not None:
            return {
                "snapshot_id": str(existing.id),
                "snapshot_status": existing.snapshot_status,
                "snapshot_token": existing.snapshot_token,
                "idempotent": True,
            }

        new_snapshot = await self._repository.insert_snapshot(
            tenant_id=tenant_id,
            organisation_id=snapshot.organisation_id,
            template_id=snapshot.template_id,
            template_version_id=snapshot.template_version_id,
            reporting_period=snapshot.reporting_period,
            upload_artifact_id=snapshot.upload_artifact_id,
            snapshot_token=next_token,
            source_file_hash=snapshot.source_file_hash,
            sheet_name=snapshot.sheet_name,
            snapshot_status=target_status,
            validation_summary_json={
                **summary,
                "derived_from_snapshot_id": str(snapshot.id),
            },
            created_by=created_by,
        )
        await self._repository.insert_normalized_lines(
            tenant_id=tenant_id,
            snapshot_id=new_snapshot.id,
            created_by=created_by,
            lines=normalized_lines,
        )

        previous_exceptions = await self._repository.list_exceptions(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
        )
        copied = [
            ValidationException(
                exception_code=item.exception_code,
                severity=item.severity,
                source_ref=item.source_ref,
                message=item.message,
            )
            for item in previous_exceptions
        ]
        if copied or new_exceptions:
            await self._repository.insert_exceptions(
                tenant_id=tenant_id,
                snapshot_id=new_snapshot.id,
                created_by=created_by,
                exceptions=[*copied, *new_exceptions],
            )

        return {
            "snapshot_id": str(new_snapshot.id),
            "snapshot_status": new_snapshot.snapshot_status,
            "snapshot_token": new_snapshot.snapshot_token,
            "exception_count": len(copied) + len(new_exceptions),
            "idempotent": False,
        }

    async def finalize_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        snapshot = await self._repository.get_snapshot(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )
        if snapshot is None:
            raise ValueError("Snapshot not found")
        if snapshot.snapshot_status != SnapshotStatus.VALIDATED.value:
            raise ValueError("Only validated snapshots can be finalized")

        template_version = await self._repository.get_template_version(
            tenant_id=tenant_id,
            template_version_id=snapshot.template_version_id,
        )
        if template_version is None:
            raise ValueError("Template version not found")

        next_token = self._snapshot_service.build_snapshot_token(
            SnapshotTokenInput(
                source_file_hash=snapshot.source_file_hash,
                sheet_name=snapshot.sheet_name,
                structure_hash=template_version.structure_hash,
                mapping_set_identity="derived",
                validation_rule_set_identity="mis_validation_v1",
                reporting_period=snapshot.reporting_period,
                template_version_id=snapshot.template_version_id,
                status=SnapshotStatus.FINALIZED.value,
            )
        )
        existing = await self._repository.get_snapshot_by_token(
            tenant_id=tenant_id,
            template_version_id=snapshot.template_version_id,
            snapshot_token=next_token,
        )
        if existing is not None:
            return {
                "snapshot_id": str(existing.id),
                "snapshot_status": existing.snapshot_status,
                "snapshot_token": existing.snapshot_token,
                "idempotent": True,
            }

        finalized = await self._repository.insert_snapshot(
            tenant_id=tenant_id,
            organisation_id=snapshot.organisation_id,
            template_id=snapshot.template_id,
            template_version_id=snapshot.template_version_id,
            reporting_period=snapshot.reporting_period,
            upload_artifact_id=snapshot.upload_artifact_id,
            snapshot_token=next_token,
            source_file_hash=snapshot.source_file_hash,
            sheet_name=snapshot.sheet_name,
            snapshot_status=SnapshotStatus.FINALIZED.value,
            validation_summary_json={
                **snapshot.validation_summary_json,
                "derived_from_snapshot_id": str(snapshot.id),
                "finalized": True,
            },
            created_by=created_by,
        )

        existing_lines = await self._repository.list_normalized_lines(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
        )
        normalized_lines = [
            NormalizedLine(
                line_no=row.line_no,
                canonical_metric_code=row.canonical_metric_code,
                canonical_dimension_json=row.canonical_dimension_json,
                source_row_ref=row.source_row_ref,
                source_column_ref=row.source_column_ref,
                period_value=row.period_value,
                currency_code=row.currency_code,
                sign_applied=row.sign_applied,
                validation_status=ValidationStatus(row.validation_status),
            )
            for row in existing_lines
        ]
        await self._repository.insert_normalized_lines(
            tenant_id=tenant_id,
            snapshot_id=finalized.id,
            created_by=created_by,
            lines=normalized_lines,
        )

        previous_exceptions = await self._repository.list_exceptions(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
        )
        copied = [
            ValidationException(
                exception_code=item.exception_code,
                severity=item.severity,
                source_ref=item.source_ref,
                message=item.message,
            )
            for item in previous_exceptions
        ]
        if copied:
            await self._repository.insert_exceptions(
                tenant_id=tenant_id,
                snapshot_id=finalized.id,
                created_by=created_by,
                exceptions=copied,
            )

        return {
            "snapshot_id": str(finalized.id),
            "snapshot_status": finalized.snapshot_status,
            "snapshot_token": finalized.snapshot_token,
            "idempotent": False,
        }

    async def list_templates(self, *, tenant_id: uuid.UUID) -> list[Any]:
        return await self._repository.list_templates(tenant_id=tenant_id)

    async def list_template_versions(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> list[Any]:
        return await self._repository.list_template_versions(
            tenant_id=tenant_id, template_id=template_id
        )

    async def get_snapshot(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> Any:
        return await self._repository.get_snapshot(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )

    async def list_snapshot_exceptions(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> list[Any]:
        return await self._repository.list_exceptions(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )

    async def get_drift_event(
        self, *, tenant_id: uuid.UUID, drift_event_id: uuid.UUID
    ) -> Any:
        return await self._repository.get_drift_event(
            tenant_id=tenant_id, drift_event_id=drift_event_id
        )

    async def list_normalized_lines(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> list[Any]:
        return await self._repository.list_normalized_lines(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )

    async def snapshot_summary(
        self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> dict[str, Any]:
        return await self._repository.summarize_snapshot(
            tenant_id=tenant_id, snapshot_id=snapshot_id
        )

    def _parse_file(
        self, *, file_name: str, file_content_base64: str, sheet_name: str | None
    ) -> dict[str, Any]:
        content = base64.b64decode(file_content_base64)
        lowered = file_name.lower()
        if lowered.endswith(".csv"):
            return parse_csv_bytes(content, sheet_name=sheet_name or "csv")
        if lowered.endswith(".xlsx"):
            return parse_excel_bytes(content, preferred_sheet=sheet_name)
        raise ValueError("Unsupported file type. Only .csv and .xlsx are supported")
