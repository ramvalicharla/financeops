from __future__ import annotations

import base64
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.core.intent.context import require_mutation_context
from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import (
    MappingService,
)
from financeops.modules.payroll_gl_normalization.application.payroll_normalization_service import (
    PayrollNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.source_detection_service import (
    SourceDetectionService,
)
from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_normalization.domain.entities import (
    GlNormalizedEntry,
    NormalizationExceptionEntry,
    PayrollNormalizedEntry,
)
from financeops.modules.payroll_gl_normalization.domain.enums import (
    ExceptionSeverity,
    LineStatus,
    RunStatus,
    RunType,
)
from financeops.modules.payroll_gl_normalization.domain.value_objects import (
    RunTokenInput,
    SourceVersionTokenInput,
)
from financeops.modules.payroll_gl_normalization.infrastructure.file_parser_csv import (
    parse_csv_bytes,
)
from financeops.modules.payroll_gl_normalization.infrastructure.file_parser_excel import (
    parse_excel_bytes,
)
from financeops.modules.payroll_gl_normalization.infrastructure.repository import (
    PayrollGlNormalizationRepository,
)
from financeops.modules.payroll_gl_normalization.infrastructure.token_builder import (
    build_run_token,
    build_source_version_token,
)
from financeops.utils.determinism import sha256_hex_bytes


class NormalizationRunService:
    def __init__(
        self,
        *,
        repository: PayrollGlNormalizationRepository,
        source_detection_service: SourceDetectionService,
        mapping_service: MappingService,
        payroll_normalization_service: PayrollNormalizationService,
        gl_normalization_service: GlNormalizationService,
        validation_service: ValidationService,
    ) -> None:
        self._repository = repository
        self._source_detection = source_detection_service
        self._mapping_service = mapping_service
        self._payroll_normalizer = payroll_normalization_service
        self._gl_normalizer = gl_normalization_service
        self._validation = validation_service

    async def detect_source(
        self,
        *,
        tenant_id: uuid.UUID,
        source_code: str,
        file_name: str,
        file_content_base64: str,
        source_family_hint: str | None,
        sheet_name: str | None,
    ) -> dict[str, Any]:
        parsed = self._parse_file(
            file_name=file_name,
            file_content_base64=file_content_base64,
            sheet_name=sheet_name,
        )
        detection = self._source_detection.detect(
            headers=parsed["headers"],
            row_labels=parsed["row_labels"],
            blank_row_density=parsed["blank_row_density"],
            formula_density=parsed["formula_density"],
            source_family_hint=source_family_hint,
        )
        mappings = self._mapping_service.propose_mappings(
            source_family=detection["source_family"],
            headers=parsed["headers"],
        )
        existing_source = await self._repository.get_source_by_code(
            tenant_id=tenant_id, source_code=source_code
        )
        return {
            "source_id": str(existing_source.id) if existing_source is not None else None,
            "source_family": detection["source_family"],
            "signature": detection["signature"],
            "detection_summary_json": {
                **detection["detection_summary_json"],
                "headers": parsed["headers"],
            },
            "proposed_mappings": mappings,
            "unmapped_headers": self._mapping_service.unmapped_headers(
                headers=parsed["headers"],
                mappings=mappings,
            ),
        }

    async def commit_source_version(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        source_family: str,
        source_code: str,
        source_name: str,
        structure_hash: str,
        header_hash: str,
        row_signature_hash: str,
        source_detection_summary_json: dict[str, Any],
        activate: bool,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        source = await self._repository.get_source_by_code(
            tenant_id=tenant_id, source_code=source_code
        )
        if source is None:
            source = await self._repository.create_source(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                source_family=source_family,
                source_code=source_code,
                source_name=source_name,
                status="active",
                created_by=created_by,
            )

        version_token = build_source_version_token(
            SourceVersionTokenInput(
                source_id=source.id,
                structure_hash=structure_hash,
                header_hash=header_hash,
                row_signature_hash=row_signature_hash,
                source_detection_summary_json=source_detection_summary_json,
            )
        )
        existing = await self._repository.get_source_version_by_token(
            tenant_id=tenant_id,
            source_id=source.id,
            version_token=version_token,
        )
        if existing is not None:
            existing_mappings = await self._repository.list_mappings(
                tenant_id=tenant_id, source_version_id=existing.id
            )
            mapping_payload = [
                {
                    "mapping_type": item.mapping_type,
                    "source_field_name": item.source_field_name,
                    "canonical_field_name": item.canonical_field_name,
                    "transform_rule": item.transform_rule,
                    "default_value_json": item.default_value_json,
                    "required_flag": item.required_flag,
                    "confidence_score": str(item.confidence_score),
                }
                for item in existing_mappings
            ]
            return {
                "source_id": str(source.id),
                "source_version_id": str(existing.id),
                "version_no": existing.version_no,
                "version_token": existing.version_token,
                "mapping_version_token": self._mapping_service.mapping_version_token(
                    mapping_payload
                ),
                "status": existing.status,
                "idempotent": True,
            }

        active = await self._repository.get_active_source_version(
            tenant_id=tenant_id, source_id=source.id
        )
        status = "active" if activate and active is None else "candidate"
        version = await self._repository.insert_source_version(
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=await self._repository.next_source_version_no(source_id=source.id),
            version_token=version_token,
            structure_hash=structure_hash,
            header_hash=header_hash,
            row_signature_hash=row_signature_hash,
            source_detection_summary_json=source_detection_summary_json,
            supersedes_id=active.id if status == "active" and active is not None else None,
            status=status,
            created_by=created_by,
        )

        headers = source_detection_summary_json.get("headers") or []
        mappings = self._mapping_service.propose_mappings(
            source_family=source_family,
            headers=[str(item) for item in headers],
        )
        mapping_rows = await self._repository.insert_mappings(
            tenant_id=tenant_id,
            source_version_id=version.id,
            created_by=created_by,
            mappings=mappings,
        )
        mapping_payload = [
            {
                "mapping_type": item.mapping_type,
                "source_field_name": item.source_field_name,
                "canonical_field_name": item.canonical_field_name,
                "transform_rule": item.transform_rule,
                "default_value_json": item.default_value_json,
                "required_flag": item.required_flag,
                "confidence_score": str(item.confidence_score),
            }
            for item in mapping_rows
        ]
        return {
            "source_id": str(source.id),
            "source_version_id": str(version.id),
            "version_no": version.version_no,
            "version_token": version.version_token,
            "mapping_version_token": self._mapping_service.mapping_version_token(
                mapping_payload
            ),
            "status": version.status,
            "idempotent": False,
        }

    async def upload_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        source_id: uuid.UUID,
        source_version_id: uuid.UUID,
        run_type: str,
        reporting_period: date,
        source_artifact_id: uuid.UUID,
        file_name: str,
        file_content_base64: str,
        sheet_name: str | None,
        created_by: uuid.UUID,
        admitted_airlock_item_id: uuid.UUID | None,
        source_type: str | None = None,
        source_external_ref: str | None = None,
    ) -> dict[str, Any]:
        mutation_context = require_mutation_context("Normalization run upload")
        await AirlockAdmissionService().assert_admitted(
            self._repository._session,
            tenant_id=tenant_id,
            item_id=admitted_airlock_item_id,
            source_type=source_type,
        )
        source = await self._repository.get_source_by_id(
            tenant_id=tenant_id, source_id=source_id
        )
        if source is None:
            raise ValueError("Normalization source not found")
        source_version = await self._repository.get_source_version(
            tenant_id=tenant_id, source_version_id=source_version_id
        )
        if source_version is None:
            raise ValueError("Normalization source version not found")
        if run_type not in {RunType.PAYROLL_NORMALIZATION.value, RunType.GL_NORMALIZATION.value}:
            raise ValueError("Unsupported run_type")

        parsed = self._parse_file(
            file_name=file_name,
            file_content_base64=file_content_base64,
            sheet_name=sheet_name,
        )
        content = base64.b64decode(file_content_base64)
        source_file_hash = sha256_hex_bytes(content)
        mapping_rows = await self._repository.list_mappings(
            tenant_id=tenant_id, source_version_id=source_version_id
        )
        mappings = [
            {
                "mapping_type": item.mapping_type,
                "source_field_name": item.source_field_name,
                "canonical_field_name": item.canonical_field_name,
                "transform_rule": item.transform_rule,
                "default_value_json": item.default_value_json,
                "required_flag": item.required_flag,
                "confidence_score": str(item.confidence_score),
            }
            for item in mapping_rows
        ]
        mapping_version_token = self._mapping_service.mapping_version_token(mappings)

        early_exceptions = self._validation.validate_upload_shape(
            run_type=run_type, headers=parsed["headers"]
        )
        payroll_lines: list[PayrollNormalizedEntry] = []
        gl_lines: list[GlNormalizedEntry] = []
        line_exceptions: list[NormalizationExceptionEntry] = []
        if run_type == RunType.PAYROLL_NORMALIZATION.value:
            payroll_lines, line_exceptions = self._payroll_normalizer.normalize(
                headers=parsed["headers"],
                rows=parsed["rows"],
                mappings=mappings,
                reporting_period=reporting_period,
            )
            line_exceptions.extend(self._validation.validate_payroll_lines(lines=payroll_lines))
        else:
            gl_lines, line_exceptions = self._gl_normalizer.normalize(
                headers=parsed["headers"],
                rows=parsed["rows"],
                mappings=mappings,
                reporting_period=reporting_period,
            )
            line_exceptions.extend(self._validation.validate_gl_lines(lines=gl_lines))
        all_exceptions = [*early_exceptions, *line_exceptions]
        summary = self._validation.summarize(exceptions=all_exceptions)

        run_token = build_run_token(
            RunTokenInput(
                source_id=source_id,
                source_version_id=source_version_id,
                mapping_version_token=mapping_version_token,
                run_type=run_type,
                reporting_period=reporting_period,
                source_file_hash=source_file_hash,
                run_status=RunStatus.PENDING.value,
            )
        )
        existing = await self._repository.get_run_by_token(
            tenant_id=tenant_id, run_token=run_token
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "run_status": existing.run_status,
                "idempotent": True,
            }

        run = await self._repository.insert_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            source_id=source_id,
            source_version_id=source_version_id,
            mapping_version_token=mapping_version_token,
            run_type=run_type,
            reporting_period=reporting_period,
            source_artifact_id=source_artifact_id,
            source_file_hash=source_file_hash,
            source_airlock_item_id=admitted_airlock_item_id,
            source_type=source_type,
            source_external_ref=source_external_ref,
            run_token=run_token,
            run_status=RunStatus.PENDING.value,
            validation_summary_json=summary,
            created_by=created_by,
            created_by_intent_id=mutation_context.intent_id,
            recorded_by_job_id=mutation_context.job_id,
        )
        evidence_links: list[dict[str, Any]] = []
        if run_type == RunType.PAYROLL_NORMALIZATION.value:
            inserted = await self._repository.insert_payroll_lines(
                tenant_id=tenant_id,
                run_id=run.id,
                created_by=created_by,
                lines=payroll_lines,
            )
            for line in inserted:
                evidence_links.append(
                    {
                        "normalized_line_type": "payroll_line",
                        "normalized_line_id": line.id,
                        "evidence_type": "source_row",
                        "evidence_ref": line.source_row_ref,
                        "evidence_label": "Payroll source row",
                    }
                )
        else:
            inserted = await self._repository.insert_gl_lines(
                tenant_id=tenant_id,
                run_id=run.id,
                created_by=created_by,
                lines=gl_lines,
            )
            for line in inserted:
                evidence_links.append(
                    {
                        "normalized_line_type": "gl_line",
                        "normalized_line_id": line.id,
                        "evidence_type": "source_row",
                        "evidence_ref": line.source_row_ref,
                        "evidence_label": "GL source row",
                    }
                )

        if all_exceptions:
            await self._repository.insert_exceptions(
                tenant_id=tenant_id,
                run_id=run.id,
                created_by=created_by,
                exceptions=all_exceptions,
            )
        if evidence_links:
            await self._repository.insert_evidence_links(
                tenant_id=tenant_id,
                run_id=run.id,
                created_by=created_by,
                links=evidence_links,
            )
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "run_status": run.run_status,
            "payroll_line_count": len(payroll_lines),
            "gl_line_count": len(gl_lines),
            "exception_count": len(all_exceptions),
            "source_airlock_item_id": str(admitted_airlock_item_id) if admitted_airlock_item_id else None,
            "intent_id": str(mutation_context.intent_id),
            "job_id": str(mutation_context.job_id),
            "idempotent": False,
        }

    async def validate_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Normalization run not found")
        exceptions = await self._repository.list_exceptions(tenant_id=tenant_id, run_id=run.id)
        summary = self._validation.summarize(
            exceptions=[
                NormalizationExceptionEntry(
                    exception_code=item.exception_code,
                    severity=self._severity_from_text(item.severity),
                    source_ref=item.source_ref,
                    message=item.message,
                )
                for item in exceptions
            ]
        )
        target_status = (
            RunStatus.FAILED.value if summary["status"] == "failed" else RunStatus.VALIDATED.value
        )
        token = build_run_token(
            RunTokenInput(
                source_id=run.source_id,
                source_version_id=run.source_version_id,
                mapping_version_token=run.mapping_version_token,
                run_type=run.run_type,
                reporting_period=run.reporting_period,
                source_file_hash=run.source_file_hash,
                run_status=target_status,
            )
        )
        existing = await self._repository.get_run_by_token(
            tenant_id=tenant_id, run_token=token
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "run_status": existing.run_status,
                "idempotent": True,
            }
        new_run = await self._repository.insert_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            source_id=run.source_id,
            source_version_id=run.source_version_id,
            mapping_version_token=run.mapping_version_token,
            run_type=run.run_type,
            reporting_period=run.reporting_period,
            source_artifact_id=run.source_artifact_id,
            source_file_hash=run.source_file_hash,
            run_token=token,
            run_status=target_status,
            validation_summary_json={**summary, "derived_from_run_id": str(run.id)},
            created_by=created_by,
        )
        await self._copy_run_outputs(
            tenant_id=tenant_id,
            from_run_id=run.id,
            to_run_id=new_run.id,
            created_by=created_by,
        )
        return {
            "run_id": str(new_run.id),
            "run_token": new_run.run_token,
            "run_status": new_run.run_status,
            "idempotent": False,
        }

    async def finalize_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Normalization run not found")
        if run.run_status != RunStatus.VALIDATED.value:
            raise ValueError("Only validated runs can be finalized")
        token = build_run_token(
            RunTokenInput(
                source_id=run.source_id,
                source_version_id=run.source_version_id,
                mapping_version_token=run.mapping_version_token,
                run_type=run.run_type,
                reporting_period=run.reporting_period,
                source_file_hash=run.source_file_hash,
                run_status=RunStatus.FINALIZED.value,
            )
        )
        existing = await self._repository.get_run_by_token(
            tenant_id=tenant_id, run_token=token
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "run_status": existing.run_status,
                "idempotent": True,
            }
        new_run = await self._repository.insert_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            source_id=run.source_id,
            source_version_id=run.source_version_id,
            mapping_version_token=run.mapping_version_token,
            run_type=run.run_type,
            reporting_period=run.reporting_period,
            source_artifact_id=run.source_artifact_id,
            source_file_hash=run.source_file_hash,
            run_token=token,
            run_status=RunStatus.FINALIZED.value,
            validation_summary_json={
                **run.validation_summary_json,
                "derived_from_run_id": str(run.id),
                "finalized": True,
            },
            created_by=created_by,
        )
        await self._copy_run_outputs(
            tenant_id=tenant_id,
            from_run_id=run.id,
            to_run_id=new_run.id,
            created_by=created_by,
        )
        return {
            "run_id": str(new_run.id),
            "run_token": new_run.run_token,
            "run_status": new_run.run_status,
            "idempotent": False,
        }

    async def get_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict[str, Any] | None:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            return None
        return {
            "id": str(run.id),
            "source_id": str(run.source_id),
            "source_version_id": str(run.source_version_id),
            "mapping_version_token": run.mapping_version_token,
            "run_type": run.run_type,
            "reporting_period": run.reporting_period.isoformat(),
            "source_artifact_id": str(run.source_artifact_id),
            "source_file_hash": run.source_file_hash,
            "run_token": run.run_token,
            "run_status": run.run_status,
            "validation_summary_json": run.validation_summary_json,
            "created_at": run.created_at.isoformat(),
        }

    async def list_run_exceptions(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_exceptions(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(item.id),
                "exception_code": item.exception_code,
                "severity": item.severity,
                "source_ref": item.source_ref,
                "message": item.message,
                "resolution_status": item.resolution_status,
                "created_at": item.created_at.isoformat(),
            }
            for item in rows
        ]

    async def list_payroll_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_payroll_lines(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(item.id),
                "row_no": item.row_no,
                "employee_code": item.employee_code,
                "employee_name": item.employee_name,
                "payroll_period": item.payroll_period.isoformat(),
                "legal_entity": item.legal_entity,
                "department": item.department,
                "cost_center": item.cost_center,
                "business_unit": item.business_unit,
                "location": item.location,
                "grade": item.grade,
                "designation": item.designation,
                "currency_code": item.currency_code,
                "canonical_metric_code": item.canonical_metric_code,
                "amount_value": str(item.amount_value),
                "source_row_ref": item.source_row_ref,
                "source_column_ref": item.source_column_ref,
                "normalization_status": item.normalization_status,
            }
            for item in rows
        ]

    async def list_gl_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_gl_lines(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(item.id),
                "row_no": item.row_no,
                "journal_id": item.journal_id,
                "journal_line_no": item.journal_line_no,
                "posting_date": item.posting_date.isoformat() if item.posting_date else None,
                "document_date": item.document_date.isoformat() if item.document_date else None,
                "posting_period": item.posting_period,
                "legal_entity": item.legal_entity,
                "account_code": item.account_code,
                "account_name": item.account_name,
                "cost_center": item.cost_center,
                "department": item.department,
                "business_unit": item.business_unit,
                "project": item.project,
                "customer": item.customer,
                "vendor": item.vendor,
                "source_module": item.source_module,
                "source_document_id": item.source_document_id,
                "currency_code": item.currency_code,
                "debit_amount": str(item.debit_amount),
                "credit_amount": str(item.credit_amount),
                "signed_amount": str(item.signed_amount),
                "local_amount": str(item.local_amount),
                "transaction_amount": str(item.transaction_amount),
                "source_row_ref": item.source_row_ref,
                "source_column_ref": item.source_column_ref,
                "normalization_status": item.normalization_status,
            }
            for item in rows
        ]

    async def run_summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        return await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)

    async def list_sources(self, *, tenant_id: uuid.UUID) -> list[Any]:
        return await self._repository.list_sources(tenant_id=tenant_id)

    async def list_source_versions(
        self, *, tenant_id: uuid.UUID, source_id: uuid.UUID
    ) -> list[Any]:
        return await self._repository.list_source_versions(
            tenant_id=tenant_id, source_id=source_id
        )

    def _parse_file(
        self, *, file_name: str, file_content_base64: str, sheet_name: str | None
    ) -> dict[str, Any]:
        content = base64.b64decode(file_content_base64)
        lower = file_name.lower()
        if lower.endswith(".csv"):
            return parse_csv_bytes(content, sheet_name=sheet_name or "csv")
        if lower.endswith(".xlsx"):
            return parse_excel_bytes(content, preferred_sheet=sheet_name)
        raise ValueError("Unsupported file type. Only .csv and .xlsx are supported")

    async def _copy_run_outputs(
        self,
        *,
        tenant_id: uuid.UUID,
        from_run_id: uuid.UUID,
        to_run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> None:
        payroll_lines = await self._repository.list_payroll_lines(
            tenant_id=tenant_id, run_id=from_run_id
        )
        if payroll_lines:
            await self._repository.insert_payroll_lines(
                tenant_id=tenant_id,
                run_id=to_run_id,
                created_by=created_by,
                lines=[
                    PayrollNormalizedEntry(
                        row_no=item.row_no,
                        employee_code=item.employee_code,
                        employee_name=item.employee_name,
                        payroll_period=item.payroll_period,
                        legal_entity=item.legal_entity,
                        department=item.department,
                        cost_center=item.cost_center,
                        business_unit=item.business_unit,
                        location=item.location,
                        grade=item.grade,
                        designation=item.designation,
                        currency_code=item.currency_code,
                        canonical_metric_code=item.canonical_metric_code,
                        amount_value=Decimal(item.amount_value),
                        source_row_ref=item.source_row_ref,
                        source_column_ref=item.source_column_ref,
                        normalization_status=self._line_status_from_text(item.normalization_status),
                    )
                    for item in payroll_lines
                ],
            )
        gl_lines = await self._repository.list_gl_lines(tenant_id=tenant_id, run_id=from_run_id)
        if gl_lines:
            await self._repository.insert_gl_lines(
                tenant_id=tenant_id,
                run_id=to_run_id,
                created_by=created_by,
                lines=[
                    GlNormalizedEntry(
                        row_no=item.row_no,
                        journal_id=item.journal_id,
                        journal_line_no=item.journal_line_no,
                        posting_date=item.posting_date,
                        document_date=item.document_date,
                        posting_period=item.posting_period,
                        legal_entity=item.legal_entity,
                        account_code=item.account_code,
                        account_name=item.account_name,
                        cost_center=item.cost_center,
                        department=item.department,
                        business_unit=item.business_unit,
                        project=item.project,
                        customer=item.customer,
                        vendor=item.vendor,
                        source_module=item.source_module,
                        source_document_id=item.source_document_id,
                        currency_code=item.currency_code,
                        debit_amount=Decimal(item.debit_amount),
                        credit_amount=Decimal(item.credit_amount),
                        signed_amount=Decimal(item.signed_amount),
                        local_amount=Decimal(item.local_amount),
                        transaction_amount=Decimal(item.transaction_amount),
                        source_row_ref=item.source_row_ref,
                        source_column_ref=item.source_column_ref,
                        normalization_status=self._line_status_from_text(item.normalization_status),
                    )
                    for item in gl_lines
                ],
            )
        exceptions = await self._repository.list_exceptions(
            tenant_id=tenant_id, run_id=from_run_id
        )
        if exceptions:
            await self._repository.insert_exceptions(
                tenant_id=tenant_id,
                run_id=to_run_id,
                created_by=created_by,
                exceptions=[
                    NormalizationExceptionEntry(
                        exception_code=item.exception_code,
                        severity=self._severity_from_text(item.severity),
                        source_ref=item.source_ref,
                        message=item.message,
                    )
                    for item in exceptions
                ],
            )

    def _severity_from_text(self, value: str) -> ExceptionSeverity:
        return ExceptionSeverity(value)

    def _line_status_from_text(self, value: str) -> LineStatus:
        return LineStatus(value)
