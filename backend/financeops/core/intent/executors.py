from __future__ import annotations

import uuid
from datetime import date
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.enums import IntentType
from financeops.db.models.intent_pipeline import CanonicalIntent
from financeops.modules.accounting_layer.application.journal_service import (
    approve_journal,
    create_journal_draft,
    post_journal,
    review_journal,
    reverse_journal,
    submit_journal,
)
from financeops.modules.accounting_layer.domain.schemas import JournalCreate


@dataclass(frozen=True)
class ExecutorResult:
    record_refs: dict[str, Any]


class BaseIntentExecutor:
    async def execute(
        self,
        db: AsyncSession,
        *,
        intent: CanonicalIntent,
    ) -> ExecutorResult:
        raise NotImplementedError


class CreateJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        payload_json = dict(intent.payload_json or {})
        payload = JournalCreate.model_validate(payload_json)
        journal = await create_journal_draft(
            db,
            tenant_id=intent.tenant_id,
            created_by=intent.requested_by_user_id,
            payload=payload,
            source=str(payload_json.get("source") or "MANUAL"),
            external_reference_id=(
                str(payload_json["external_reference_id"])
                if payload_json.get("external_reference_id") is not None
                else None
            ),
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(journal.id),
                "journal_number": journal.journal_number,
                "status": journal.status,
            }
        )


class SubmitJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        if intent.target_id is None:
            raise ValidationError("SUBMIT_JOURNAL intent requires a target journal.")
        result = await submit_journal(
            db,
            tenant_id=intent.tenant_id,
            journal_id=intent.target_id,
            acted_by=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status})


class ReviewJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        if intent.target_id is None:
            raise ValidationError("REVIEW_JOURNAL intent requires a target journal.")
        result = await review_journal(
            db,
            tenant_id=intent.tenant_id,
            journal_id=intent.target_id,
            acted_by=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status})


class ApproveJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        if intent.target_id is None:
            raise ValidationError("APPROVE_JOURNAL intent requires a target journal.")
        result = await approve_journal(
            db,
            tenant_id=intent.tenant_id,
            journal_id=intent.target_id,
            acted_by=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status})


class PostJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        if intent.target_id is None:
            raise ValidationError("POST_JOURNAL intent requires a target journal.")
        result = await post_journal(
            db,
            tenant_id=intent.tenant_id,
            journal_id=intent.target_id,
            acted_by=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(result.id),
                "status": result.status,
                "posted_at": result.posted_at.isoformat() if result.posted_at else None,
            }
        )


class ReverseJournalExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        if intent.target_id is None:
            raise ValidationError("REVERSE_JOURNAL intent requires a target journal.")
        journal = await reverse_journal(
            db,
            tenant_id=intent.tenant_id,
            journal_id=intent.target_id,
            acted_by=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(journal.id),
                "journal_number": journal.journal_number,
                "status": journal.status,
                "reversed_target_id": str(intent.target_id),
            }
        )


def _uuid_value(payload: dict[str, Any], key: str) -> uuid.UUID:
    raw = payload.get(key)
    if raw in {None, ""}:
        raise ValidationError(f"{key} is required for governed external mutation.")
    return uuid.UUID(str(raw))


class CreateErpSyncRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.erp_sync.application.sync_service import SyncService
        from financeops.modules.erp_sync.domain.enums import DatasetType

        payload = dict(intent.payload_json or {})
        file_content_base64 = str(payload.get("file_content_base64") or "").strip()
        content = b""
        if file_content_base64:
            import base64

            content = base64.b64decode(file_content_base64)
        result = await SyncService(db).trigger_sync_run(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            entity_id=uuid.UUID(str(payload["entity_id"])) if payload.get("entity_id") else None,
            connection_id=_uuid_value(payload, "connection_id"),
            sync_definition_id=_uuid_value(payload, "sync_definition_id"),
            sync_definition_version_id=_uuid_value(payload, "sync_definition_version_id"),
            dataset_type=DatasetType(str(payload["dataset_type"])),
            idempotency_key=str(intent.idempotency_key),
            created_by=intent.requested_by_user_id,
            extraction_kwargs={
                "content": content,
                "filename": str(payload.get("file_name") or "data.csv"),
                "checkpoint": payload.get("checkpoint"),
            },
            admitted_airlock_item_id=_uuid_value(payload, "admitted_airlock_item_id"),
            source_type=str(payload.get("source_type") or "erp_sync_request"),
            source_external_ref=str(payload.get("source_external_ref") or payload.get("connection_id") or ""),
        )
        return ExecutorResult(record_refs=result)


class CreateNormalizationRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
            GlNormalizationService,
        )
        from financeops.modules.payroll_gl_normalization.application.mapping_service import (
            MappingService,
        )
        from financeops.modules.payroll_gl_normalization.application.payroll_normalization_service import (
            PayrollNormalizationService,
        )
        from financeops.modules.payroll_gl_normalization.application.run_service import (
            NormalizationRunService,
        )
        from financeops.modules.payroll_gl_normalization.application.source_detection_service import (
            SourceDetectionService,
        )
        from financeops.modules.payroll_gl_normalization.application.validation_service import (
            ValidationService,
        )
        from financeops.modules.payroll_gl_normalization.infrastructure.repository import (
            PayrollGlNormalizationRepository,
        )

        payload = dict(intent.payload_json or {})
        result = await NormalizationRunService(
            repository=PayrollGlNormalizationRepository(db),
            source_detection_service=SourceDetectionService(),
            mapping_service=MappingService(),
            payroll_normalization_service=PayrollNormalizationService(),
            gl_normalization_service=GlNormalizationService(),
            validation_service=ValidationService(),
        ).upload_run(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            source_id=_uuid_value(payload, "source_id"),
            source_version_id=_uuid_value(payload, "source_version_id"),
            run_type=str(payload["run_type"]),
            reporting_period=date.fromisoformat(str(payload["reporting_period"])),
            source_artifact_id=_uuid_value(payload, "source_artifact_id"),
            file_name=str(payload["file_name"]),
            file_content_base64=str(payload["file_content_base64"]),
            sheet_name=str(payload["sheet_name"]) if payload.get("sheet_name") is not None else None,
            created_by=intent.requested_by_user_id,
            admitted_airlock_item_id=_uuid_value(payload, "admitted_airlock_item_id"),
            source_type=str(payload.get("source_type") or "normalization_upload"),
            source_external_ref=str(payload.get("source_external_ref") or payload.get("source_id") or ""),
        )
        return ExecutorResult(record_refs=result)


class MutationExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, BaseIntentExecutor] = {
            IntentType.CREATE_JOURNAL.value: CreateJournalExecutor(),
            IntentType.SUBMIT_JOURNAL.value: SubmitJournalExecutor(),
            IntentType.REVIEW_JOURNAL.value: ReviewJournalExecutor(),
            IntentType.APPROVE_JOURNAL.value: ApproveJournalExecutor(),
            IntentType.POST_JOURNAL.value: PostJournalExecutor(),
            IntentType.REVERSE_JOURNAL.value: ReverseJournalExecutor(),
            IntentType.CREATE_ERP_SYNC_RUN.value: CreateErpSyncRunExecutor(),
            IntentType.CREATE_NORMALIZATION_RUN.value: CreateNormalizationRunExecutor(),
        }

    def resolve(self, intent_type: str) -> BaseIntentExecutor:
        executor = self._executors.get(intent_type)
        if executor is None:
            raise ValidationError(f"No executor is registered for intent type '{intent_type}'.")
        return executor
