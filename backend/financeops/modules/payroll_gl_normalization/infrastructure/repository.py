from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payroll_gl_normalization import (
    GlNormalizedLine,
    NormalizationEvidenceLink,
    NormalizationException,
    NormalizationMapping,
    NormalizationRun,
    NormalizationSource,
    NormalizationSourceVersion,
    PayrollNormalizedLine,
)
from financeops.modules.payroll_gl_normalization.domain.entities import (
    GlNormalizedEntry,
    NormalizationExceptionEntry,
    PayrollNormalizedEntry,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class PayrollGlNormalizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_source_by_code(
        self, *, tenant_id: uuid.UUID, source_code: str
    ) -> NormalizationSource | None:
        result = await self._session.execute(
            select(NormalizationSource).where(
                NormalizationSource.tenant_id == tenant_id,
                NormalizationSource.source_code == source_code,
            )
        )
        return result.scalar_one_or_none()

    async def get_source_by_id(
        self, *, tenant_id: uuid.UUID, source_id: uuid.UUID
    ) -> NormalizationSource | None:
        result = await self._session.execute(
            select(NormalizationSource).where(
                NormalizationSource.tenant_id == tenant_id,
                NormalizationSource.id == source_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_sources(self, *, tenant_id: uuid.UUID) -> list[NormalizationSource]:
        result = await self._session.execute(
            select(NormalizationSource)
            .where(NormalizationSource.tenant_id == tenant_id)
            .order_by(NormalizationSource.created_at.desc(), NormalizationSource.id.desc())
        )
        return list(result.scalars().all())

    async def create_source(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        source_family: str,
        source_code: str,
        source_name: str,
        status: str,
        created_by: uuid.UUID,
    ) -> NormalizationSource:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=NormalizationSource,
            tenant_id=tenant_id,
            record_data={
                "source_family": source_family,
                "source_code": source_code,
                "source_name": source_name,
            },
            values={
                "organisation_id": organisation_id,
                "source_family": source_family,
                "source_code": source_code,
                "source_name": source_name,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="normalization.source.created",
                resource_type="normalization_source",
                resource_name=source_code,
            ),
        )

    async def get_source_version_by_token(
        self,
        *,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        version_token: str,
    ) -> NormalizationSourceVersion | None:
        result = await self._session.execute(
            select(NormalizationSourceVersion).where(
                NormalizationSourceVersion.tenant_id == tenant_id,
                NormalizationSourceVersion.source_id == source_id,
                NormalizationSourceVersion.version_token == version_token,
            )
        )
        return result.scalar_one_or_none()

    async def next_source_version_no(self, *, source_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(NormalizationSourceVersion.version_no)).where(
                NormalizationSourceVersion.source_id == source_id
            )
        )
        return int(result.scalar_one_or_none() or 0) + 1

    async def get_active_source_version(
        self, *, tenant_id: uuid.UUID, source_id: uuid.UUID
    ) -> NormalizationSourceVersion | None:
        result = await self._session.execute(
            select(NormalizationSourceVersion)
            .where(
                NormalizationSourceVersion.tenant_id == tenant_id,
                NormalizationSourceVersion.source_id == source_id,
                NormalizationSourceVersion.status == "active",
            )
            .order_by(
                NormalizationSourceVersion.created_at.desc(),
                NormalizationSourceVersion.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_source_version(
        self, *, tenant_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> NormalizationSourceVersion | None:
        result = await self._session.execute(
            select(NormalizationSourceVersion).where(
                NormalizationSourceVersion.tenant_id == tenant_id,
                NormalizationSourceVersion.id == source_version_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_source_versions(
        self, *, tenant_id: uuid.UUID, source_id: uuid.UUID
    ) -> list[NormalizationSourceVersion]:
        result = await self._session.execute(
            select(NormalizationSourceVersion)
            .where(
                NormalizationSourceVersion.tenant_id == tenant_id,
                NormalizationSourceVersion.source_id == source_id,
            )
            .order_by(
                NormalizationSourceVersion.version_no.desc(),
                NormalizationSourceVersion.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def insert_source_version(
        self,
        *,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        version_no: int,
        version_token: str,
        structure_hash: str,
        header_hash: str,
        row_signature_hash: str,
        source_detection_summary_json: dict[str, Any],
        supersedes_id: uuid.UUID | None,
        status: str,
        created_by: uuid.UUID,
    ) -> NormalizationSourceVersion:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=NormalizationSourceVersion,
            tenant_id=tenant_id,
            record_data={
                "source_id": str(source_id),
                "version_no": version_no,
                "version_token": version_token,
            },
            values={
                "source_id": source_id,
                "version_no": version_no,
                "version_token": version_token,
                "structure_hash": structure_hash,
                "header_hash": header_hash,
                "row_signature_hash": row_signature_hash,
                "source_detection_summary_json": source_detection_summary_json,
                "supersedes_id": supersedes_id,
                "status": status,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="normalization.source_version.created",
                resource_type="normalization_source_version",
                resource_name=str(source_id),
            ),
        )

    async def list_mappings(
        self, *, tenant_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> list[NormalizationMapping]:
        result = await self._session.execute(
            select(NormalizationMapping)
            .where(
                NormalizationMapping.tenant_id == tenant_id,
                NormalizationMapping.source_version_id == source_version_id,
            )
            .order_by(
                NormalizationMapping.mapping_type.asc(),
                NormalizationMapping.source_field_name.asc(),
                NormalizationMapping.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def insert_mappings(
        self,
        *,
        tenant_id: uuid.UUID,
        source_version_id: uuid.UUID,
        created_by: uuid.UUID,
        mappings: Iterable[dict[str, Any]],
    ) -> list[NormalizationMapping]:
        rows: list[NormalizationMapping] = []
        for item in mappings:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=NormalizationMapping,
                tenant_id=tenant_id,
                record_data={
                    "source_version_id": str(source_version_id),
                    "mapping_type": item["mapping_type"],
                    "source_field_name": item["source_field_name"],
                    "canonical_field_name": item["canonical_field_name"],
                },
                values={
                    "source_version_id": source_version_id,
                    "mapping_type": item["mapping_type"],
                    "source_field_name": item["source_field_name"],
                    "canonical_field_name": item["canonical_field_name"],
                    "transform_rule": item.get("transform_rule"),
                    "default_value_json": item.get("default_value_json", {}),
                    "required_flag": bool(item.get("required_flag", False)),
                    "confidence_score": item.get("confidence_score", "1.0000"),
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def get_run_by_token(
        self, *, tenant_id: uuid.UUID, run_token: str
    ) -> NormalizationRun | None:
        result = await self._session.execute(
            select(NormalizationRun).where(
                NormalizationRun.tenant_id == tenant_id,
                NormalizationRun.run_token == run_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> NormalizationRun | None:
        result = await self._session.execute(
            select(NormalizationRun).where(
                NormalizationRun.tenant_id == tenant_id,
                NormalizationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def insert_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        source_id: uuid.UUID,
        source_version_id: uuid.UUID,
        mapping_version_token: str,
        run_type: str,
        reporting_period: date,
        source_artifact_id: uuid.UUID,
        source_file_hash: str,
        run_token: str,
        run_status: str,
        validation_summary_json: dict[str, Any],
        created_by: uuid.UUID,
    ) -> NormalizationRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=NormalizationRun,
            tenant_id=tenant_id,
            record_data={
                "source_id": str(source_id),
                "source_version_id": str(source_version_id),
                "run_type": run_type,
                "run_token": run_token,
            },
            values={
                "organisation_id": organisation_id,
                "source_id": source_id,
                "source_version_id": source_version_id,
                "mapping_version_token": mapping_version_token,
                "run_type": run_type,
                "reporting_period": reporting_period,
                "source_artifact_id": source_artifact_id,
                "source_file_hash": source_file_hash,
                "run_token": run_token,
                "run_status": run_status,
                "validation_summary_json": validation_summary_json,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="normalization.run.created",
                resource_type="normalization_run",
                resource_name=run_type,
            ),
        )

    async def insert_payroll_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        created_by: uuid.UUID,
        lines: Iterable[PayrollNormalizedEntry],
    ) -> list[PayrollNormalizedLine]:
        rows: list[PayrollNormalizedLine] = []
        for item in lines:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=PayrollNormalizedLine,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "row_no": item.row_no,
                    "canonical_metric_code": item.canonical_metric_code,
                    "amount_value": str(item.amount_value),
                },
                values={
                    "run_id": run_id,
                    "row_no": item.row_no,
                    "employee_code": item.employee_code,
                    "employee_name": item.employee_name,
                    "payroll_period": item.payroll_period,
                    "legal_entity": item.legal_entity,
                    "department": item.department,
                    "cost_center": item.cost_center,
                    "business_unit": item.business_unit,
                    "location": item.location,
                    "grade": item.grade,
                    "designation": item.designation,
                    "currency_code": item.currency_code,
                    "canonical_metric_code": item.canonical_metric_code,
                    "amount_value": item.amount_value,
                    "source_row_ref": item.source_row_ref,
                    "source_column_ref": item.source_column_ref,
                    "normalization_status": item.normalization_status.value,
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_payroll_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[PayrollNormalizedLine]:
        result = await self._session.execute(
            select(PayrollNormalizedLine)
            .where(
                PayrollNormalizedLine.tenant_id == tenant_id,
                PayrollNormalizedLine.run_id == run_id,
            )
            .order_by(PayrollNormalizedLine.row_no.asc(), PayrollNormalizedLine.id.asc())
        )
        return list(result.scalars().all())

    async def insert_gl_lines(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        created_by: uuid.UUID,
        lines: Iterable[GlNormalizedEntry],
    ) -> list[GlNormalizedLine]:
        rows: list[GlNormalizedLine] = []
        for item in lines:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=GlNormalizedLine,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "row_no": item.row_no,
                    "account_code": item.account_code,
                    "signed_amount": str(item.signed_amount),
                },
                values={
                    "run_id": run_id,
                    "row_no": item.row_no,
                    "journal_id": item.journal_id,
                    "journal_line_no": item.journal_line_no,
                    "posting_date": item.posting_date,
                    "document_date": item.document_date,
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
                    "debit_amount": item.debit_amount,
                    "credit_amount": item.credit_amount,
                    "signed_amount": item.signed_amount,
                    "local_amount": item.local_amount,
                    "transaction_amount": item.transaction_amount,
                    "source_row_ref": item.source_row_ref,
                    "source_column_ref": item.source_column_ref,
                    "normalization_status": item.normalization_status.value,
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_gl_lines(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[GlNormalizedLine]:
        result = await self._session.execute(
            select(GlNormalizedLine)
            .where(
                GlNormalizedLine.tenant_id == tenant_id,
                GlNormalizedLine.run_id == run_id,
            )
            .order_by(GlNormalizedLine.row_no.asc(), GlNormalizedLine.id.asc())
        )
        return list(result.scalars().all())

    async def insert_exceptions(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        created_by: uuid.UUID,
        exceptions: Iterable[NormalizationExceptionEntry],
    ) -> list[NormalizationException]:
        rows: list[NormalizationException] = []
        for item in exceptions:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=NormalizationException,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "exception_code": item.exception_code,
                    "severity": item.severity.value,
                },
                values={
                    "run_id": run_id,
                    "exception_code": item.exception_code,
                    "severity": item.severity.value,
                    "source_ref": item.source_ref,
                    "message": item.message,
                    "resolution_status": "open",
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def list_exceptions(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[NormalizationException]:
        result = await self._session.execute(
            select(NormalizationException)
            .where(
                NormalizationException.tenant_id == tenant_id,
                NormalizationException.run_id == run_id,
            )
            .order_by(NormalizationException.created_at.asc(), NormalizationException.id.asc())
        )
        return list(result.scalars().all())

    async def insert_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        created_by: uuid.UUID,
        links: Iterable[dict[str, Any]],
    ) -> list[NormalizationEvidenceLink]:
        rows: list[NormalizationEvidenceLink] = []
        for item in links:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=NormalizationEvidenceLink,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "normalized_line_type": item["normalized_line_type"],
                    "normalized_line_id": str(item["normalized_line_id"]),
                    "evidence_ref": item["evidence_ref"],
                },
                values={
                    "run_id": run_id,
                    "normalized_line_type": item["normalized_line_type"],
                    "normalized_line_id": item["normalized_line_id"],
                    "evidence_type": item["evidence_type"],
                    "evidence_ref": item["evidence_ref"],
                    "evidence_label": item["evidence_label"],
                    "created_by": created_by,
                },
            )
            rows.append(row)
        return rows

    async def summarize_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict[str, Any]:
        payroll_count = (
            await self._session.execute(
                select(func.count(PayrollNormalizedLine.id)).where(
                    PayrollNormalizedLine.tenant_id == tenant_id,
                    PayrollNormalizedLine.run_id == run_id,
                )
            )
        ).scalar_one()
        gl_count = (
            await self._session.execute(
                select(func.count(GlNormalizedLine.id)).where(
                    GlNormalizedLine.tenant_id == tenant_id,
                    GlNormalizedLine.run_id == run_id,
                )
            )
        ).scalar_one()
        exception_count = (
            await self._session.execute(
                select(func.count(NormalizationException.id)).where(
                    NormalizationException.tenant_id == tenant_id,
                    NormalizationException.run_id == run_id,
                )
            )
        ).scalar_one()
        return {
            "payroll_line_count": int(payroll_count or 0),
            "gl_line_count": int(gl_count or 0),
            "exception_count": int(exception_count or 0),
        }
