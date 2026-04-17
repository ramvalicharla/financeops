from __future__ import annotations

from dataclasses import dataclass
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.enums import IntentStatus, IntentType
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
    final_status: str | None = None


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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(journal.id),
            trigger_event="journal_created",
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(journal.id),
                "journal_number": journal.journal_number,
                "status": journal.status,
                **snapshot_refs,
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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(result.id),
            trigger_event="journal_submitted",
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status, **snapshot_refs})


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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(result.id),
            trigger_event="journal_reviewed",
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status, **snapshot_refs})


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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(result.id),
            trigger_event="journal_approved",
        )
        return ExecutorResult(record_refs={"journal_id": str(result.id), "status": result.status, **snapshot_refs})


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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(result.id),
            trigger_event="journal_posted",
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(result.id),
                "status": result.status,
                "posted_at": result.posted_at.isoformat() if result.posted_at else None,
                **snapshot_refs,
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
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="journal",
            subject_id=str(journal.id),
            trigger_event="journal_reversed",
        )
        return ExecutorResult(
            record_refs={
                "journal_id": str(journal.id),
                "journal_number": journal.journal_number,
                "status": journal.status,
                "reversed_target_id": str(intent.target_id),
                **snapshot_refs,
            }
        )


def _uuid_value(payload: dict[str, Any], key: str) -> uuid.UUID:
    raw = payload.get(key)
    if raw in {None, ""}:
        raise ValidationError(f"{key} is required for governed external mutation.")
    return uuid.UUID(str(raw))


def _decimal_value(payload: dict[str, Any], key: str) -> Decimal:
    raw = payload.get(key)
    if raw in {None, ""}:
        raise ValidationError(f"{key} is required for governed financial mutation.")
    return Decimal(str(raw))


def _optional_uuid_value(payload: dict[str, Any], key: str) -> uuid.UUID | None:
    raw = payload.get(key)
    if raw in {None, ""}:
        return None
    return uuid.UUID(str(raw))


def _optional_date_value(payload: dict[str, Any], key: str) -> date | None:
    raw = payload.get(key)
    if raw in {None, ""}:
        return None
    return date.fromisoformat(str(raw))


async def _snapshot_refs(
    db: AsyncSession,
    *,
    intent: CanonicalIntent,
    subject_type: str,
    subject_id: str,
    trigger_event: str,
) -> dict[str, str | None]:
    from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

    try:
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type=subject_type,
            subject_id=subject_id,
            trigger_event=trigger_event,
        )
    except ValueError:
        return {
            "snapshot_id": None,
            "determinism_hash": None,
        }
    return {
        "snapshot_id": str(snapshot.id),
        "determinism_hash": snapshot.determinism_hash,
    }


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
        sync_run_id = str(result.get("sync_run_id") or "")
        if sync_run_id:
            result = {
                **result,
                **await _snapshot_refs(
                    db,
                    intent=intent,
                    subject_type="erp_sync_run",
                    subject_id=sync_run_id,
                    trigger_event="erp_sync_run_created",
                ),
            }
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


class ImportBankStatementExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.bank_reconciliation.parsers.base import BankTransaction as ParsedBankTransaction
        from financeops.services.bank_recon_service import store_bank_transactions

        payload = dict(intent.payload_json or {})
        transactions = [
            ParsedBankTransaction(
                transaction_date=date.fromisoformat(str(row["transaction_date"])),
                value_date=_optional_date_value(row, "value_date"),
                description=str(row["description"]),
                reference=str(row.get("reference") or ""),
                debit=Decimal(str(row["debit"])) if row.get("debit") not in {None, ""} else None,
                credit=Decimal(str(row["credit"])) if row.get("credit") not in {None, ""} else None,
                balance=Decimal(str(row["balance"])) if row.get("balance") not in {None, ""} else None,
                transaction_type=str(row.get("transaction_type") or "OTHER"),
            )
            for row in payload.get("transactions", [])
        ]
        stored = await store_bank_transactions(
            db,
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            entity_name=str(payload.get("entity_name") or ""),
            bank_name=str(payload["bank_name"]),
            transactions=transactions,
            uploaded_by=intent.requested_by_user_id,
            admitted_airlock_item_id=_uuid_value(payload, "admitted_airlock_item_id"),
            source_type=str(payload.get("source_type") or "bank_recon_statement_upload"),
        )
        statement_id = str(stored[0].statement_id) if stored else None
        return ExecutorResult(
            record_refs={
                "statement_id": statement_id,
                "transaction_count": len(stored),
            }
        )


class CreateBankStatementExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.bank_recon_service import create_bank_statement

        payload = dict(intent.payload_json or {})
        stmt = await create_bank_statement(
            db,
            tenant_id=intent.tenant_id,
            bank_name=str(payload["bank_name"]),
            account_number_masked=str(payload["account_number_masked"]),
            currency=str(payload["currency"]),
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            entity_name=str(payload.get("entity_name") or "") or None,
            opening_balance=_decimal_value(payload, "opening_balance"),
            closing_balance=_decimal_value(payload, "closing_balance"),
            file_name=str(payload["file_name"]),
            file_hash=str(payload["file_hash"]),
            uploaded_by=intent.requested_by_user_id,
            transaction_count=int(payload.get("transaction_count") or 0),
            location_id=_optional_uuid_value(payload, "location_id"),
            cost_centre_id=_optional_uuid_value(payload, "cost_centre_id"),
        )
        return ExecutorResult(
            record_refs={
                "statement_id": str(stmt.id),
                "status": stmt.status,
                "bank_name": stmt.bank_name,
            }
        )


class AddBankTransactionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.bank_recon_service import add_bank_transaction

        payload = dict(intent.payload_json or {})
        txn = await add_bank_transaction(
            db,
            tenant_id=intent.tenant_id,
            statement_id=_uuid_value(payload, "statement_id"),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            transaction_date=date.fromisoformat(str(payload["transaction_date"])),
            description=str(payload["description"]),
            debit_amount=_decimal_value(payload, "debit_amount"),
            credit_amount=_decimal_value(payload, "credit_amount"),
            balance=_decimal_value(payload, "balance"),
            reference=str(payload.get("reference") or "") or None,
        )
        return ExecutorResult(
            record_refs={
                "transaction_id": str(txn.id),
                "statement_id": str(txn.statement_id),
                "match_status": txn.match_status,
            }
        )


class RunBankReconciliationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.bank_recon_service import run_bank_reconciliation

        payload = dict(intent.payload_json or {})
        statement_id = _uuid_value(payload, "statement_id")
        result = await run_bank_reconciliation(
            db,
            tenant_id=intent.tenant_id,
            statement_id=statement_id,
            run_by=intent.requested_by_user_id,
            force_rerun=bool(payload.get("force_rerun", False)),
        )
        return ExecutorResult(
            record_refs={
                "statement_id": str(statement_id),
                "item_ids": [str(item.id) for item in result.items],
                "open_items_created": len(result.items),
                "matched": result.summary.matched,
                "near_match": result.summary.near_match,
                "fuzzy": result.summary.fuzzy,
                "bank_only": result.summary.bank_only,
                "gl_only": result.summary.gl_only,
                "net_difference": str(result.summary.net_difference),
            }
        )


class PrepareGstReturnExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.gst_service import create_gst_return

        payload = dict(intent.payload_json or {})
        row = await create_gst_return(
            db,
            tenant_id=intent.tenant_id,
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            entity_name=str(payload.get("entity_name") or "") or None,
            gstin=str(payload["gstin"]),
            return_type=str(payload["return_type"]),
            taxable_value=_decimal_value(payload, "taxable_value"),
            igst_amount=_decimal_value(payload, "igst_amount"),
            cgst_amount=_decimal_value(payload, "cgst_amount"),
            sgst_amount=_decimal_value(payload, "sgst_amount"),
            cess_amount=Decimal(str(payload.get("cess_amount") or "0")),
            filing_date=_optional_date_value(payload, "filing_date"),
            notes=str(payload.get("notes") or "") or None,
            location_id=_optional_uuid_value(payload, "location_id"),
            cost_centre_id=_optional_uuid_value(payload, "cost_centre_id"),
            created_by=intent.requested_by_user_id,
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="gst_return",
            subject_id=str(row.id),
            trigger_event="gst_return_prepared",
        )
        return ExecutorResult(
            record_refs={
                "return_id": str(row.id),
                "status": row.status,
                "return_type": row.return_type,
                **snapshot_refs,
            }
        )


class SubmitGstReturnExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.gst_service import submit_gst_return

        payload = dict(intent.payload_json or {})
        if intent.target_id is None:
            raise ValidationError("SUBMIT_GST_RETURN intent requires a target GST return.")
        row = await submit_gst_return(
            db,
            tenant_id=intent.tenant_id,
            return_id=intent.target_id,
            filed_by=intent.requested_by_user_id,
            filing_date=_optional_date_value(payload, "filing_date"),
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="gst_return",
            subject_id=str(row.id),
            trigger_event="gst_return_submitted",
        )
        return ExecutorResult(record_refs={"return_id": str(row.id), "status": row.status, **snapshot_refs})


class RunGstReconciliationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.gst_service import run_gst_reconciliation

        payload = dict(intent.payload_json or {})
        items = await run_gst_reconciliation(
            db,
            tenant_id=intent.tenant_id,
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            entity_name=str(payload.get("entity_name") or "") or None,
            return_type_a=str(payload["return_type_a"]),
            return_type_b=str(payload["return_type_b"]),
            run_by=intent.requested_by_user_id,
        )
        return ExecutorResult(
            record_refs={
                "item_ids": [str(item.id) for item in items],
                "breaks_found": len(items),
            }
        )


class CreateFixedAssetClassExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        payload = dict(intent.payload_json or {})
        data = {key: value for key, value in payload.items() if key != "entity_id"}
        for key in (
            "coa_asset_account_id",
            "coa_accum_dep_account_id",
            "coa_dep_expense_account_id",
        ):
            if data.get(key) not in {None, ""}:
                data[key] = uuid.UUID(str(data[key]))
        row = await FixedAssetService(db).create_asset_class(
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            data=data,
        )
        return ExecutorResult(record_refs={"asset_class_id": str(row.id), "is_active": row.is_active})


class UpdateFixedAssetClassExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        if intent.target_id is None:
            raise ValidationError("UPDATE_FIXED_ASSET_CLASS intent requires a target asset class.")
        data = dict(intent.payload_json or {})
        for key in (
            "coa_asset_account_id",
            "coa_accum_dep_account_id",
            "coa_dep_expense_account_id",
        ):
            if data.get(key) not in {None, ""}:
                data[key] = uuid.UUID(str(data[key]))
        row = await FixedAssetService(db).update_asset_class(
            tenant_id=intent.tenant_id,
            class_id=intent.target_id,
            data=data,
        )
        return ExecutorResult(record_refs={"asset_class_id": str(row.id), "is_active": row.is_active})


class CreateFixedAssetExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        payload = dict(intent.payload_json or {})
        data = {key: value for key, value in payload.items() if key != "entity_id"}
        for key in (
            "asset_class_id",
            "location_id",
            "cost_centre_id",
        ):
            if data.get(key) not in {None, ""}:
                data[key] = uuid.UUID(str(data[key]))
        for key in ("purchase_date", "capitalisation_date"):
            if data.get(key) not in {None, ""}:
                data[key] = date.fromisoformat(str(data[key]))
        row = await FixedAssetService(db).create_asset(
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            data=data,
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="fixed_asset",
            subject_id=str(row.id),
            trigger_event="fixed_asset_created",
        )
        return ExecutorResult(record_refs={"asset_id": str(row.id), "status": row.status, **snapshot_refs})


class UpdateFixedAssetExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        if intent.target_id is None:
            raise ValidationError("UPDATE_FIXED_ASSET intent requires a target asset.")
        payload = dict(intent.payload_json or {})
        for key in ("location_id", "cost_centre_id"):
            if payload.get(key) not in {None, ""}:
                payload[key] = uuid.UUID(str(payload[key]))
        if payload.get("disposal_date") not in {None, ""}:
            payload["disposal_date"] = date.fromisoformat(str(payload["disposal_date"]))
        row = await FixedAssetService(db).update_asset(
            tenant_id=intent.tenant_id,
            asset_id=intent.target_id,
            data=payload,
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="fixed_asset",
            subject_id=str(row.id),
            trigger_event="fixed_asset_updated",
        )
        return ExecutorResult(record_refs={"asset_id": str(row.id), "status": row.status, **snapshot_refs})


class RunFixedAssetDepreciationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        payload = dict(intent.payload_json or {})
        service = FixedAssetService(db)
        if intent.target_id is not None:
            row = await service.run_asset_depreciation(
                tenant_id=intent.tenant_id,
                asset_id=intent.target_id,
                period_start=date.fromisoformat(str(payload["period_start"])),
                period_end=date.fromisoformat(str(payload["period_end"])),
                gaap=str(payload.get("gaap") or "INDAS"),
            )
            return ExecutorResult(record_refs={"run_id": str(row.id), "asset_id": str(row.asset_id)})
        rows = await service.run_depreciation(
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            period_start=date.fromisoformat(str(payload["period_start"])),
            period_end=date.fromisoformat(str(payload["period_end"])),
            gaap=str(payload.get("gaap") or "INDAS"),
        )
        return ExecutorResult(record_refs={"run_ids": [str(row.id) for row in rows], "count": len(rows)})


class RunFixedAssetWorkflowExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.config import settings
        from financeops.services.fixed_assets.service_facade import create_run
        from financeops.temporal.fixed_assets_workflows import (
            FixedAssetsWorkflow,
            FixedAssetsWorkflowInput,
        )

        payload = dict(intent.payload_json or {})
        request_payload = dict(payload.get("request_payload") or {})
        correlation_id = str(payload.get("correlation_id") or "")
        run = await create_run(
            db,
            tenant_id=intent.tenant_id,
            initiated_by=intent.requested_by_user_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
        if run["created_new"]:
            from financeops.core.intent.dispatcher import JobDispatcher

            await JobDispatcher().start_temporal_workflow(
                FixedAssetsWorkflow.run,
                FixedAssetsWorkflowInput(
                    run_id=str(run["run_id"]),
                    tenant_id=str(intent.tenant_id),
                    correlation_id=correlation_id,
                    requested_by=str(intent.requested_by_user_id),
                    config_hash=str(run["request_signature"]),
                ),
                workflow_id=str(run["workflow_id"]),
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(minutes=20),
            )
        return ExecutorResult(
            record_refs={
                "run_id": str(run["run_id"]),
                "workflow_id": str(run["workflow_id"]),
                "status": "accepted" if run["created_new"] else str(run["status"]),
                "created_new": bool(run["created_new"]),
                "correlation_id": correlation_id,
            }
        )


class PostFixedAssetRevaluationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        if intent.target_id is None:
            raise ValidationError("POST_FIXED_ASSET_REVALUATION intent requires a target asset.")
        payload = dict(intent.payload_json or {})
        row = await FixedAssetService(db).post_revaluation(
            tenant_id=intent.tenant_id,
            asset_id=intent.target_id,
            fair_value=_decimal_value(payload, "fair_value"),
            method=str(payload["method"]),
            revaluation_date=date.fromisoformat(str(payload["revaluation_date"])),
        )
        return ExecutorResult(record_refs={"revaluation_id": str(row.id), "asset_id": str(row.asset_id)})


class PostFixedAssetImpairmentExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        if intent.target_id is None:
            raise ValidationError("POST_FIXED_ASSET_IMPAIRMENT intent requires a target asset.")
        payload = dict(intent.payload_json or {})
        row = await FixedAssetService(db).post_impairment(
            tenant_id=intent.tenant_id,
            asset_id=intent.target_id,
            value_in_use=Decimal(str(payload["value_in_use"])) if payload.get("value_in_use") not in {None, ""} else None,
            fvlcts=Decimal(str(payload["fvlcts"])) if payload.get("fvlcts") not in {None, ""} else None,
            discount_rate=Decimal(str(payload["discount_rate"])) if payload.get("discount_rate") not in {None, ""} else None,
            impairment_date=date.fromisoformat(str(payload["impairment_date"])),
        )
        return ExecutorResult(record_refs={"impairment_id": str(row.id), "asset_id": str(row.asset_id)})


class DisposeFixedAssetExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService

        if intent.target_id is None:
            raise ValidationError("DISPOSE_FIXED_ASSET intent requires a target asset.")
        payload = dict(intent.payload_json or {})
        row = await FixedAssetService(db).dispose_asset(
            tenant_id=intent.tenant_id,
            asset_id=intent.target_id,
            disposal_date=date.fromisoformat(str(payload["disposal_date"])),
            proceeds=_decimal_value(payload, "proceeds"),
        )
        return ExecutorResult(record_refs={"asset_id": str(row.id), "status": row.status})


class CreatePrepaidScheduleExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService

        payload = dict(intent.payload_json or {})
        data = {key: value for key, value in payload.items() if key != "entity_id"}
        for key in (
            "coa_prepaid_account_id",
            "coa_expense_account_id",
            "location_id",
            "cost_centre_id",
        ):
            if data.get(key) not in {None, ""}:
                data[key] = uuid.UUID(str(data[key]))
        for key in ("coverage_start", "coverage_end"):
            if data.get(key) not in {None, ""}:
                data[key] = date.fromisoformat(str(data[key]))
        row = await PrepaidService(db).create_schedule(
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            data=data,
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="prepaid_schedule",
            subject_id=str(row.id),
            trigger_event="prepaid_schedule_created",
        )
        return ExecutorResult(record_refs={"schedule_id": str(row.id), "status": row.status, **snapshot_refs})


class UpdatePrepaidScheduleExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService

        if intent.target_id is None:
            raise ValidationError("UPDATE_PREPAID_SCHEDULE intent requires a target schedule.")
        data = dict(intent.payload_json or {})
        for key in (
            "coa_prepaid_account_id",
            "coa_expense_account_id",
            "location_id",
            "cost_centre_id",
        ):
            if data.get(key) not in {None, ""}:
                data[key] = uuid.UUID(str(data[key]))
        for key in ("coverage_start", "coverage_end"):
            if data.get(key) not in {None, ""}:
                data[key] = date.fromisoformat(str(data[key]))
        row = await PrepaidService(db).update_schedule(
            tenant_id=intent.tenant_id,
            schedule_id=intent.target_id,
            data=data,
        )
        snapshot_refs = await _snapshot_refs(
            db,
            intent=intent,
            subject_type="prepaid_schedule",
            subject_id=str(row.id),
            trigger_event="prepaid_schedule_updated",
        )
        return ExecutorResult(record_refs={"schedule_id": str(row.id), "status": row.status, **snapshot_refs})


class PostPrepaidAmortizationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService

        payload = dict(intent.payload_json or {})
        rows = await PrepaidService(db).run_period(
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            period_start=date.fromisoformat(str(payload["period_start"])),
            period_end=date.fromisoformat(str(payload["period_end"])),
        )
        return ExecutorResult(record_refs={"entry_ids": [str(row.id) for row in rows], "count": len(rows)})


class RunPrepaidWorkflowExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.config import settings
        from financeops.services.prepaid.service_facade import create_run
        from financeops.temporal.prepaid_workflows import (
            PrepaidAmortizationWorkflow,
            PrepaidAmortizationWorkflowInput,
        )

        payload = dict(intent.payload_json or {})
        request_payload = dict(payload.get("request_payload") or {})
        correlation_id = str(payload.get("correlation_id") or "")
        run = await create_run(
            db,
            tenant_id=intent.tenant_id,
            initiated_by=intent.requested_by_user_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
        if run["created_new"]:
            from financeops.core.intent.dispatcher import JobDispatcher

            await JobDispatcher().start_temporal_workflow(
                PrepaidAmortizationWorkflow.run,
                PrepaidAmortizationWorkflowInput(
                    run_id=str(run["run_id"]),
                    tenant_id=str(intent.tenant_id),
                    correlation_id=correlation_id,
                    requested_by=str(intent.requested_by_user_id),
                    config_hash=str(run["request_signature"]),
                ),
                workflow_id=str(run["workflow_id"]),
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(minutes=15),
            )
        return ExecutorResult(
            record_refs={
                "run_id": str(run["run_id"]),
                "workflow_id": str(run["workflow_id"]),
                "status": "accepted" if run["created_new"] else str(run["status"]),
                "created_new": bool(run["created_new"]),
                "correlation_id": correlation_id,
            }
        )


class StartLegacyConsolidationRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.config import settings
        from financeops.services.consolidation import EntitySnapshotMapping, create_or_get_run
        from financeops.temporal.consolidation_workflows import (
            ConsolidationWorkflow,
            ConsolidationWorkflowInput,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        correlation_id = str(payload.get("correlation_id") or "")
        run = await create_or_get_run(
            db,
            tenant_id=intent.tenant_id,
            initiated_by=intent.requested_by_user_id,
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            parent_currency=str(payload["parent_currency"]),
            rate_mode=str(payload["rate_mode"]),
            mappings=[
                EntitySnapshotMapping(
                    entity_id=uuid.UUID(str(item["entity_id"])),
                    snapshot_id=uuid.UUID(str(item["snapshot_id"])),
                )
                for item in payload.get("entity_snapshots", [])
            ],
            amount_tolerance_parent=(
                Decimal(str(payload["amount_tolerance_parent"]))
                if payload.get("amount_tolerance_parent") not in {None, ""}
                else None
            ),
            fx_explained_tolerance_parent=(
                Decimal(str(payload["fx_explained_tolerance_parent"]))
                if payload.get("fx_explained_tolerance_parent") not in {None, ""}
                else None
            ),
            timing_tolerance_days=int(payload["timing_tolerance_days"])
            if payload.get("timing_tolerance_days") not in {None, ""}
            else None,
            correlation_id=correlation_id,
        )
        if run.created_new:
            from financeops.core.intent.dispatcher import JobDispatcher

            await JobDispatcher().start_temporal_workflow(
                ConsolidationWorkflow.run,
                ConsolidationWorkflowInput(
                    run_id=str(run.run_id),
                    tenant_id=str(intent.tenant_id),
                    correlation_id=correlation_id,
                    requested_by=str(intent.requested_by_user_id),
                    config_hash=str(run.request_signature),
                ),
                workflow_id=str(run.workflow_id),
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                execution_timeout=timedelta(minutes=15),
            )
        await db.flush()
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="run",
            subject_id=str(run.run_id),
            trigger_event="legacy_consolidation_run_accepted",
        )
        return ExecutorResult(
            record_refs={
                "run_id": str(run.run_id),
                "workflow_id": str(run.workflow_id),
                "status": "accepted" if run.created_new else str(run.status),
                "created_new": bool(run.created_new),
                "correlation_id": correlation_id,
                "determinism_hash": snapshot.determinism_hash,
                "snapshot_refs": [str(snapshot.id)],
            }
        )


class RunConsolidationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.multi_entity_consolidation.application.adjustment_service import AdjustmentService
        from financeops.modules.multi_entity_consolidation.application.aggregation_service import AggregationService
        from financeops.modules.multi_entity_consolidation.application.hierarchy_service import HierarchyService
        from financeops.modules.multi_entity_consolidation.application.intercompany_service import IntercompanyService
        from financeops.modules.multi_entity_consolidation.application.run_service import RunService
        from financeops.modules.multi_entity_consolidation.application.validation_service import ValidationService
        from financeops.modules.multi_entity_consolidation.infrastructure.repository import MultiEntityConsolidationRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        service = RunService(
            repository=MultiEntityConsolidationRepository(db),
            validation_service=ValidationService(),
            hierarchy_service=HierarchyService(),
            aggregation_service=AggregationService(),
            intercompany_service=IntercompanyService(),
            adjustment_service=AdjustmentService(),
        )
        result = await service.create_run(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            reporting_period=date.fromisoformat(str(payload["reporting_period"])),
            source_run_refs=list(payload.get("source_run_refs") or []),
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="multi_entity_consolidation_run",
            subject_id=str(result["run_id"]),
            trigger_event="consolidation_run_created",
        )
        return ExecutorResult(
            record_refs={
                **result,
                "determinism_hash": snapshot.determinism_hash,
                "snapshot_refs": [str(snapshot.id)],
            }
        )


class ExecuteConsolidationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.multi_entity_consolidation.application.adjustment_service import AdjustmentService
        from financeops.modules.multi_entity_consolidation.application.aggregation_service import AggregationService
        from financeops.modules.multi_entity_consolidation.application.hierarchy_service import HierarchyService
        from financeops.modules.multi_entity_consolidation.application.intercompany_service import IntercompanyService
        from financeops.modules.multi_entity_consolidation.application.run_service import RunService
        from financeops.modules.multi_entity_consolidation.application.validation_service import ValidationService
        from financeops.modules.multi_entity_consolidation.infrastructure.repository import MultiEntityConsolidationRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("EXECUTE_CONSOLIDATION intent requires a target run.")
        service = RunService(
            repository=MultiEntityConsolidationRepository(db),
            validation_service=ValidationService(),
            hierarchy_service=HierarchyService(),
            aggregation_service=AggregationService(),
            intercompany_service=IntercompanyService(),
            adjustment_service=AdjustmentService(),
        )
        result = await service.execute_run(
            tenant_id=intent.tenant_id,
            run_id=intent.target_id,
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="multi_entity_consolidation_run",
            subject_id=str(intent.target_id),
            trigger_event="consolidation_run_complete",
        )
        return ExecutorResult(
            record_refs={
                **result,
                "determinism_hash": snapshot.determinism_hash,
                "snapshot_refs": [str(snapshot.id)],
            }
        )


class CreateReportDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.custom_report_builder.domain.filter_dsl import ReportDefinitionSchema
        from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        schema = ReportDefinitionSchema.model_validate(payload)
        repo = ReportRepository()
        row = await repo.create_definition(
            db=db,
            tenant_id=intent.tenant_id,
            schema=schema,
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="report_definition",
            subject_id=str(row.id),
            trigger_event="report_definition_created",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class UpdateReportDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("UPDATE_REPORT_DEFINITION intent requires a target definition.")
        payload = dict(intent.payload_json or {})
        repo = ReportRepository()
        row = await repo.update_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=intent.target_id,
            updates=dict(payload.get("updates") or {}),
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="report_definition",
            subject_id=str(row.id),
            trigger_event="report_definition_updated",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class DeactivateReportDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("DEACTIVATE_REPORT_DEFINITION intent requires a target definition.")
        repo = ReportRepository()
        row = await repo.deactivate_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=intent.target_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="report_definition",
            subject_id=str(row.id),
            trigger_event="report_definition_deactivated",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class GenerateReportExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
        from financeops.modules.custom_report_builder.tasks import run_custom_report_task

        payload = dict(intent.payload_json or {})
        repo = ReportRepository()
        definition = await repo.get_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=_uuid_value(payload, "definition_id"),
        )
        if definition is None:
            raise ValidationError("Definition not found")
        if not definition.is_active:
            raise ValidationError("Definition is inactive")
        create_run_kwargs = {
            "db": db,
            "tenant_id": intent.tenant_id,
            "definition_id": definition.id,
            "triggered_by": intent.requested_by_user_id,
            "run_metadata": {
                "intent_id": str(intent.id),
                "job_id": str(intent.job_id) if intent.job_id else None,
            },
        }
        try:
            run = await repo.create_run(**create_run_kwargs)
        except TypeError as exc:
            if "run_metadata" not in str(exc):
                raise
            create_run_kwargs.pop("run_metadata", None)
            run = await repo.create_run(**create_run_kwargs)
        from financeops.core.intent.dispatcher import JobDispatcher

        JobDispatcher().enqueue_task(run_custom_report_task, str(run.id), str(intent.tenant_id))
        return ExecutorResult(
            record_refs={"run_id": str(run.id), "definition_id": str(definition.id), "status": run.status}
        )


class CreateBoardPackDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_generator.domain.pack_definition import PackDefinitionSchema
        from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        schema = PackDefinitionSchema.model_validate(payload)
        repo = BoardPackRepository()
        row = await repo.create_definition(
            db=db,
            tenant_id=intent.tenant_id,
            schema=schema,
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_definition",
            subject_id=str(row.id),
            trigger_event="board_pack_definition_created",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class CreateBoardPackNarrativeDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
            DefinitionVersionTokenInput,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
            build_definition_version_token,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
        row = await BoardPackNarrativeRepository(db).create_board_pack_definition(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            board_pack_code=str(payload["board_pack_code"]),
            board_pack_name=str(payload["board_pack_name"]),
            audience_scope=str(payload.get("audience_scope") or "board"),
            section_order_json=dict(payload.get("section_order_json") or {}),
            inclusion_config_json=dict(payload.get("inclusion_config_json") or {}),
            version_token=version_token,
            effective_from=date.fromisoformat(str(payload["effective_from"])),
            effective_to=(
                date.fromisoformat(str(payload["effective_to"]))
                if payload.get("effective_to") not in {None, ""}
                else None
            ),
            supersedes_id=_optional_uuid_value(payload, "supersedes_id"),
            status=str(payload.get("status") or "candidate"),
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_definition",
            subject_id=str(row.id),
            trigger_event="board_pack_narrative_definition_created",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "version_token": row.version_token,
                "status": row.status,
            }
        )


class CreateBoardPackSectionDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
            DefinitionVersionTokenInput,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
            build_definition_version_token,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
        row = await BoardPackNarrativeRepository(db).create_section_definition(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            section_code=str(payload["section_code"]),
            section_name=str(payload["section_name"]),
            section_type=str(payload["section_type"]),
            render_logic_json=dict(payload.get("render_logic_json") or {}),
            section_order_default=int(payload["section_order_default"]),
            narrative_template_ref=(
                None if payload.get("narrative_template_ref") in {None, ""} else str(payload["narrative_template_ref"])
            ),
            risk_inclusion_rule_json=dict(payload.get("risk_inclusion_rule_json") or {}),
            anomaly_inclusion_rule_json=dict(payload.get("anomaly_inclusion_rule_json") or {}),
            metric_inclusion_rule_json=dict(payload.get("metric_inclusion_rule_json") or {}),
            version_token=version_token,
            effective_from=date.fromisoformat(str(payload["effective_from"])),
            effective_to=(
                date.fromisoformat(str(payload["effective_to"]))
                if payload.get("effective_to") not in {None, ""}
                else None
            ),
            supersedes_id=_optional_uuid_value(payload, "supersedes_id"),
            status=str(payload.get("status") or "candidate"),
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_section_definition",
            subject_id=str(row.id),
            trigger_event="board_pack_section_definition_created",
        )
        return ExecutorResult(
            record_refs={
                "section_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "version_token": row.version_token,
                "status": row.status,
            }
        )


class CreateNarrativeTemplateExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
            DefinitionVersionTokenInput,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
            build_definition_version_token,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
        row = await BoardPackNarrativeRepository(db).create_narrative_template(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            template_code=str(payload["template_code"]),
            template_name=str(payload["template_name"]),
            template_type=str(payload["template_type"]),
            template_text=str(payload["template_text"]),
            template_body_json=dict(payload.get("template_body_json") or {}),
            placeholder_schema_json=dict(payload.get("placeholder_schema_json") or {}),
            version_token=version_token,
            effective_from=date.fromisoformat(str(payload["effective_from"])),
            effective_to=(
                date.fromisoformat(str(payload["effective_to"]))
                if payload.get("effective_to") not in {None, ""}
                else None
            ),
            supersedes_id=_optional_uuid_value(payload, "supersedes_id"),
            status=str(payload.get("status") or "candidate"),
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="narrative_template",
            subject_id=str(row.id),
            trigger_event="narrative_template_created",
        )
        return ExecutorResult(
            record_refs={
                "template_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "version_token": row.version_token,
                "status": row.status,
            }
        )


class CreateBoardPackInclusionRuleExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
            DefinitionVersionTokenInput,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
            build_definition_version_token,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
        row = await BoardPackNarrativeRepository(db).create_inclusion_rule(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            rule_code=str(payload["rule_code"]),
            rule_name=str(payload["rule_name"]),
            rule_type=str(payload["rule_type"]),
            inclusion_logic_json=dict(payload.get("inclusion_logic_json") or {}),
            version_token=version_token,
            effective_from=date.fromisoformat(str(payload["effective_from"])),
            effective_to=(
                date.fromisoformat(str(payload["effective_to"]))
                if payload.get("effective_to") not in {None, ""}
                else None
            ),
            supersedes_id=_optional_uuid_value(payload, "supersedes_id"),
            status=str(payload.get("status") or "candidate"),
            created_by=intent.requested_by_user_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_inclusion_rule",
            subject_id=str(row.id),
            trigger_event="board_pack_inclusion_rule_created",
        )
        return ExecutorResult(
            record_refs={
                "rule_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "version_token": row.version_token,
                "status": row.status,
            }
        )


class CreateBoardPackNarrativeRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
            InclusionService,
        )
        from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
            NarrativeService,
        )
        from financeops.modules.board_pack_narrative_engine.application.run_service import RunService
        from financeops.modules.board_pack_narrative_engine.application.section_service import (
            SectionService,
        )
        from financeops.modules.board_pack_narrative_engine.application.validation_service import (
            ValidationService,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        payload = dict(intent.payload_json or {})
        service = RunService(
            repository=BoardPackNarrativeRepository(db),
            validation_service=ValidationService(),
            inclusion_service=InclusionService(),
            section_service=SectionService(),
            narrative_service=NarrativeService(),
        )
        result = await service.create_run(
            tenant_id=intent.tenant_id,
            organisation_id=_uuid_value(payload, "organisation_id"),
            reporting_period=date.fromisoformat(str(payload["reporting_period"])),
            source_metric_run_ids=[uuid.UUID(str(value)) for value in list(payload.get("source_metric_run_ids") or [])],
            source_risk_run_ids=[uuid.UUID(str(value)) for value in list(payload.get("source_risk_run_ids") or [])],
            source_anomaly_run_ids=[uuid.UUID(str(value)) for value in list(payload.get("source_anomaly_run_ids") or [])],
            created_by=intent.requested_by_user_id,
        )
        run_id = uuid.UUID(str(result["run_id"]))
        await db.flush()
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_run",
            subject_id=str(run_id),
            trigger_event="board_pack_narrative_run_created",
        )
        return ExecutorResult(
            record_refs={
                **result,
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
            }
        )


class ExecuteBoardPackNarrativeRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
            InclusionService,
        )
        from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
            NarrativeService,
        )
        from financeops.modules.board_pack_narrative_engine.application.run_service import RunService
        from financeops.modules.board_pack_narrative_engine.application.section_service import (
            SectionService,
        )
        from financeops.modules.board_pack_narrative_engine.application.validation_service import (
            ValidationService,
        )
        from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
            BoardPackNarrativeRepository,
        )
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("EXECUTE_BOARD_PACK_NARRATIVE_RUN intent requires a target run.")
        service = RunService(
            repository=BoardPackNarrativeRepository(db),
            validation_service=ValidationService(),
            inclusion_service=InclusionService(),
            section_service=SectionService(),
            narrative_service=NarrativeService(),
        )
        result = await service.execute_run(
            tenant_id=intent.tenant_id,
            run_id=intent.target_id,
            actor_user_id=intent.requested_by_user_id,
        )
        await db.flush()
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_run",
            subject_id=str(intent.target_id),
            trigger_event="board_pack_narrative_run_executed",
        )
        return ExecutorResult(
            record_refs={
                **result,
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
            }
        )


class UpdateBoardPackDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("UPDATE_BOARD_PACK_DEFINITION intent requires a target definition.")
        payload = dict(intent.payload_json or {})
        updates = dict(payload.get("updates") or {})
        if "section_types" in updates and updates["section_types"] is not None:
            updates["section_types"] = [str(value) for value in updates["section_types"]]
        repo = BoardPackRepository()
        row = await repo.update_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=intent.target_id,
            updates=updates,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_definition",
            subject_id=str(row.id),
            trigger_event="board_pack_definition_updated",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class DeactivateBoardPackDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        if intent.target_id is None:
            raise ValidationError("DEACTIVATE_BOARD_PACK_DEFINITION intent requires a target definition.")
        repo = BoardPackRepository()
        row = await repo.deactivate_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=intent.target_id,
        )
        snapshot = await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=intent.tenant_id,
            actor_user_id=intent.requested_by_user_id,
            actor_role=intent.requested_by_role,
            subject_type="board_pack_definition",
            subject_id=str(row.id),
            trigger_event="board_pack_definition_deactivated",
        )
        return ExecutorResult(
            record_refs={
                "definition_id": str(row.id),
                "snapshot_id": str(snapshot.id),
                "determinism_hash": snapshot.determinism_hash,
                "is_active": bool(row.is_active),
            }
        )


class GenerateBoardPackExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository
        from financeops.modules.board_pack_generator.tasks import generate_board_pack_task

        payload = dict(intent.payload_json or {})
        repo = BoardPackRepository()
        definition = await repo.get_definition(
            db=db,
            tenant_id=intent.tenant_id,
            definition_id=_uuid_value(payload, "definition_id"),
        )
        if definition is None:
            raise ValidationError("Definition not found")
        if not definition.is_active:
            raise ValidationError("Definition is inactive")
        create_run_kwargs = {
            "db": db,
            "tenant_id": intent.tenant_id,
            "definition_id": definition.id,
            "period_start": date.fromisoformat(str(payload["period_start"])),
            "period_end": date.fromisoformat(str(payload["period_end"])),
            "triggered_by": intent.requested_by_user_id,
            "run_metadata": {
                "intent_id": str(intent.id),
                "job_id": str(intent.job_id) if intent.job_id else None,
            },
        }
        try:
            run = await repo.create_run(**create_run_kwargs)
        except TypeError as exc:
            if "run_metadata" not in str(exc):
                raise
            create_run_kwargs.pop("run_metadata", None)
            run = await repo.create_run(**create_run_kwargs)
        from financeops.core.intent.dispatcher import JobDispatcher

        JobDispatcher().enqueue_task(generate_board_pack_task, str(run.id), str(intent.tenant_id))
        return ExecutorResult(
            record_refs={"run_id": str(run.id), "definition_id": str(definition.id), "status": run.status}
        )


class CreateWorkingCapitalSnapshotExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.working_capital_service import create_snapshot

        payload = dict(intent.payload_json or {})
        row = await create_snapshot(
            db,
            tenant_id=intent.tenant_id,
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            entity_name=str(payload["entity_name"]),
            created_by=intent.requested_by_user_id,
            cash_and_equivalents=Decimal(str(payload.get("cash_and_equivalents") or "0")),
            accounts_receivable=Decimal(str(payload.get("accounts_receivable") or "0")),
            inventory=Decimal(str(payload.get("inventory") or "0")),
            prepaid_expenses=Decimal(str(payload.get("prepaid_expenses") or "0")),
            other_current_assets=Decimal(str(payload.get("other_current_assets") or "0")),
            accounts_payable=Decimal(str(payload.get("accounts_payable") or "0")),
            accrued_liabilities=Decimal(str(payload.get("accrued_liabilities") or "0")),
            short_term_debt=Decimal(str(payload.get("short_term_debt") or "0")),
            other_current_liabilities=Decimal(str(payload.get("other_current_liabilities") or "0")),
            currency=str(payload.get("currency") or "USD"),
            notes=str(payload.get("notes") or "") or None,
        )
        return ExecutorResult(
            record_refs={
                "snapshot_id": str(row.id),
                "entity_name": row.entity_name,
                "working_capital": str(row.working_capital),
                "current_ratio": str(row.current_ratio),
                "quick_ratio": str(row.quick_ratio),
                "cash_ratio": str(row.cash_ratio),
            }
        )


class CreateBudgetVersionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.budgeting.service import create_budget_version

        payload = dict(intent.payload_json or {})
        row = await create_budget_version(
            db,
            tenant_id=intent.tenant_id,
            fiscal_year=int(payload["fiscal_year"]),
            version_name=str(payload["version_name"]),
            created_by=intent.requested_by_user_id,
            copy_from_version_id=_optional_uuid_value(payload, "copy_from_version_id"),
        )
        return ExecutorResult(
            record_refs={
                "version_id": str(row.id),
                "status": row.status,
                "version_number": row.version_number,
            }
        )


class UpsertBudgetLineExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.budgeting.service import upsert_budget_line

        payload = dict(intent.payload_json or {})
        row = await upsert_budget_line(
            db,
            tenant_id=intent.tenant_id,
            budget_version_id=_uuid_value(payload, "budget_version_id"),
            mis_line_item=str(payload["mis_line_item"]),
            mis_category=str(payload["mis_category"]),
            monthly_values=[Decimal(str(value)) for value in list(payload.get("monthly_values") or [])],
            basis=str(payload["basis"]) if payload.get("basis") not in {None, ""} else None,
            entity_id=_optional_uuid_value(payload, "entity_id"),
            requester_user_id=intent.requested_by_user_id,
            requester_user_role=intent.requested_by_role,
        )
        return ExecutorResult(
            record_refs={
                "line_id": str(row.id),
                "budget_version_id": str(row.budget_version_id),
                "mis_line_item": row.mis_line_item,
            }
        )


class SubmitBudgetVersionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.budgeting.service import submit_budget

        payload = dict(intent.payload_json or {})
        row = await submit_budget(
            db,
            tenant_id=intent.tenant_id,
            budget_version_id=_uuid_value(payload, "budget_version_id"),
            submitted_by=intent.requested_by_user_id,
        )
        return ExecutorResult(
            record_refs={
                "version_id": str(row.id),
                "status": row.status,
            }
        )


class ApproveBudgetVersionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.budgeting.service import approve_budget

        payload = dict(intent.payload_json or {})
        row = await approve_budget(
            db,
            tenant_id=intent.tenant_id,
            budget_version_id=_uuid_value(payload, "budget_version_id"),
            approved_by=intent.requested_by_user_id,
            approval_level=str(payload.get("approval_level") or "board"),
        )
        return ExecutorResult(
            record_refs={
                "version_id": str(row.id),
                "status": row.status,
                "is_board_approved": bool(row.is_board_approved),
            }
        )


class ComputeWorkingCapitalSnapshotExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.working_capital.service import compute_wc_snapshot

        payload = dict(intent.payload_json or {})
        row = await compute_wc_snapshot(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            requester_user_id=intent.requested_by_user_id,
            requester_user_role=intent.requested_by_role,
        )
        return ExecutorResult(
            record_refs={
                "snapshot_id": str(row.id),
                "period": row.period,
                "entity_id": str(row.entity_id) if row.entity_id else None,
            }
        )


class CreateChecklistTemplateExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.closing_checklist.service import create_template

        payload = dict(intent.payload_json or {})
        template = await create_template(
            db,
            tenant_id=intent.tenant_id,
            name=str(payload["name"]),
            description=str(payload["description"]) if payload.get("description") not in {None, ""} else None,
            is_default=bool(payload.get("is_default", False)),
            created_by=intent.requested_by_user_id,
            tasks=list(payload.get("tasks") or []),
        )
        return ExecutorResult(
            record_refs={
                "template_id": str(template.id),
                "name": template.name,
                "is_default": bool(template.is_default),
            }
        )


class EnsureChecklistRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.closing_checklist.service import get_or_create_run

        payload = dict(intent.payload_json or {})
        run = await get_or_create_run(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            created_by=intent.requested_by_user_id,
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(
            record_refs={
                "run_id": str(run.id),
                "period": run.period,
                "status": run.status,
            }
        )


class UpdateChecklistTaskStatusExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.closing_checklist.service import update_task_status

        payload = dict(intent.payload_json or {})
        task = await update_task_status(
            db,
            tenant_id=intent.tenant_id,
            run_id=_uuid_value(payload, "run_id"),
            task_id=_uuid_value(payload, "task_id"),
            new_status=str(payload["status"]),
            updated_by=intent.requested_by_user_id,
            notes=str(payload["notes"]) if payload.get("notes") not in {None, ""} else None,
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(
            record_refs={
                "task_id": str(task.id),
                "run_id": str(task.run_id),
                "status": task.status,
            }
        )


class AssignChecklistTaskExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.closing_checklist.service import assign_task_to_user

        payload = dict(intent.payload_json or {})
        task = await assign_task_to_user(
            db,
            tenant_id=intent.tenant_id,
            run_id=_uuid_value(payload, "run_id"),
            task_id=_uuid_value(payload, "task_id"),
            assignee_id=_uuid_value(payload, "user_id"),
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(
            record_refs={
                "task_id": str(task.id),
                "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            }
        )


class AutoCompleteChecklistTasksExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.closing_checklist.service import auto_complete_task

        payload = dict(intent.payload_json or {})
        rows = await auto_complete_task(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            event=str(payload["event"]),
        )
        return ExecutorResult(
            record_refs={
                "period": str(payload["period"]),
                "event": str(payload["event"]),
                "task_ids": [str(row.id) for row in rows],
            }
        )


class CreateMonthendChecklistExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.monthend_service import create_checklist

        payload = dict(intent.payload_json or {})
        row = await create_checklist(
            db,
            tenant_id=intent.tenant_id,
            period_year=int(payload["period_year"]),
            period_month=int(payload["period_month"]),
            entity_name=str(payload["entity_name"]),
            created_by=intent.requested_by_user_id,
            notes=str(payload["notes"]) if payload.get("notes") not in {None, ""} else None,
            add_default_tasks=bool(payload.get("add_default_tasks", True)),
        )
        return ExecutorResult(
            record_refs={
                "checklist_id": str(row.id),
                "status": row.status,
            }
        )


class AddMonthendTaskExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.monthend_service import add_task

        payload = dict(intent.payload_json or {})
        row = await add_task(
            db,
            tenant_id=intent.tenant_id,
            checklist_id=_uuid_value(payload, "checklist_id"),
            task_name=str(payload["task_name"]),
            task_category=str(payload.get("task_category") or "other"),
            priority=str(payload.get("priority") or "medium"),
            sort_order=int(payload.get("sort_order") or 0),
            description=str(payload["description"]) if payload.get("description") not in {None, ""} else None,
            assigned_to=_optional_uuid_value(payload, "assigned_to"),
            due_date=_optional_date_value(payload, "due_date"),
            is_required=bool(payload.get("is_required", True)),
        )
        return ExecutorResult(
            record_refs={
                "task_id": str(row.id),
                "checklist_id": str(row.checklist_id),
                "status": row.status,
            }
        )


class UpdateMonthendTaskStatusExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.monthend_service import update_task_status

        payload = dict(intent.payload_json or {})
        row = await update_task_status(
            db,
            tenant_id=intent.tenant_id,
            task_id=_uuid_value(payload, "task_id"),
            status=str(payload["status"]),
            completed_by=intent.requested_by_user_id if str(payload["status"]).lower() == "completed" else None,
            notes=str(payload["notes"]) if payload.get("notes") not in {None, ""} else None,
        )
        if row is None:
            raise ValidationError("Month-end task not found")
        return ExecutorResult(
            record_refs={
                "task_id": str(row.id),
                "status": row.status,
            }
        )


class CloseMonthendChecklistExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.services.monthend_service import close_checklist

        payload = dict(intent.payload_json or {})
        row = await close_checklist(
            db,
            tenant_id=intent.tenant_id,
            checklist_id=_uuid_value(payload, "checklist_id"),
            closed_by=intent.requested_by_user_id,
            notes=str(payload["notes"]) if payload.get("notes") not in {None, ""} else None,
        )
        if row is None:
            raise ValidationError("Month-end checklist not found")
        return ExecutorResult(
            record_refs={
                "checklist_id": str(row.id),
                "status": row.status,
            }
        )


class CreateForecastRunExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.forecasting.service import create_forecast_run

        payload = dict(intent.payload_json or {})
        row = await create_forecast_run(
            db,
            tenant_id=intent.tenant_id,
            run_name=str(payload["run_name"]),
            forecast_type=str(payload["forecast_type"]),
            base_period=str(payload["base_period"]),
            horizon_months=int(payload["horizon_months"]),
            created_by=intent.requested_by_user_id,
        )
        return ExecutorResult(record_refs={"run_id": str(row.id), "status": row.status})


class UpdateForecastAssumptionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.forecasting.service import update_assumption

        payload = dict(intent.payload_json or {})
        row = await update_assumption(
            db,
            tenant_id=intent.tenant_id,
            forecast_run_id=_uuid_value(payload, "forecast_run_id"),
            assumption_key=str(payload["assumption_key"]),
            new_value=Decimal(str(payload["new_value"])),
            basis=str(payload["basis"]) if payload.get("basis") not in {None, ""} else None,
        )
        return ExecutorResult(
            record_refs={
                "run_id": str(row.forecast_run_id),
                "assumption_id": str(row.id),
                "assumption_key": row.assumption_key,
            }
        )


class ComputeForecastLinesExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.forecasting.service import compute_forecast_lines

        payload = dict(intent.payload_json or {})
        rows = await compute_forecast_lines(
            db,
            tenant_id=intent.tenant_id,
            forecast_run_id=_uuid_value(payload, "forecast_run_id"),
        )
        return ExecutorResult(
            record_refs={
                "run_id": str(payload["forecast_run_id"]),
                "line_items_created": len(rows),
            }
        )


class PublishForecastExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.forecasting.service import publish_forecast

        payload = dict(intent.payload_json or {})
        row = await publish_forecast(
            db,
            tenant_id=intent.tenant_id,
            forecast_run_id=_uuid_value(payload, "forecast_run_id"),
            published_by=intent.requested_by_user_id,
        )
        return ExecutorResult(record_refs={"run_id": str(row.id), "status": row.status})


class ComputeTaxProvisionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.tax_provision.service import compute_tax_provision

        payload = dict(intent.payload_json or {})
        row = await compute_tax_provision(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            applicable_tax_rate=Decimal(str(payload["applicable_tax_rate"])),
            created_by=intent.requested_by_user_id,
            requester_user_id=intent.requested_by_user_id,
            requester_user_role=intent.requested_by_role,
        )
        return ExecutorResult(record_refs={"run_id": str(row.id), "period": row.period})


class UpsertTaxPositionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.tax_provision.service import upsert_tax_position

        payload = dict(intent.payload_json or {})
        row = await upsert_tax_position(
            db,
            tenant_id=intent.tenant_id,
            position_name=str(payload["position_name"]),
            position_type=str(payload["position_type"]),
            carrying_amount=Decimal(str(payload["carrying_amount"])),
            tax_base=Decimal(str(payload["tax_base"])),
            is_asset=bool(payload["is_asset"]),
            tax_rate=Decimal(str(payload.get("tax_rate") or "0.2500")),
            description=str(payload["description"]) if payload.get("description") not in {None, ""} else None,
        )
        return ExecutorResult(record_refs={"position_id": str(row.id), "position_name": row.position_name})


class CreateCashFlowForecastExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.cash_flow_forecast.service import create_forecast_run, seed_from_historical

        payload = dict(intent.payload_json or {})
        row = await create_forecast_run(
            db,
            tenant_id=intent.tenant_id,
            run_name=str(payload["run_name"]),
            base_date=date.fromisoformat(str(payload["base_date"])),
            opening_cash_balance=Decimal(str(payload["opening_cash_balance"])),
            currency=str(payload.get("currency") or "INR"),
            created_by=intent.requested_by_user_id,
            entity_id=_optional_uuid_value(payload, "entity_id"),
            location_id=_optional_uuid_value(payload, "location_id"),
            cost_centre_id=_optional_uuid_value(payload, "cost_centre_id"),
            weeks=int(payload.get("weeks") or 13),
        )
        if bool(payload.get("seed_historical", True)):
            await seed_from_historical(db, intent.tenant_id, row.id)
        return ExecutorResult(record_refs={"run_id": str(row.id), "status": row.status})


class UpdateCashFlowWeekExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.cash_flow_forecast.service import update_week_assumptions

        payload = dict(intent.payload_json or {})
        row = await update_week_assumptions(
            db,
            tenant_id=intent.tenant_id,
            forecast_run_id=_uuid_value(payload, "forecast_run_id"),
            week_number=int(payload["week_number"]),
            assumption_updates=dict(payload.get("assumption_updates") or {}),
        )
        return ExecutorResult(
            record_refs={
                "run_id": str(row.forecast_run_id),
                "week_id": str(row.id),
                "week_number": row.week_number,
            }
        )


class PublishCashFlowForecastExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.cash_flow_forecast.service import publish_forecast

        payload = dict(intent.payload_json or {})
        row = await publish_forecast(
            db,
            tenant_id=intent.tenant_id,
            forecast_run_id=_uuid_value(payload, "forecast_run_id"),
            published_by=intent.requested_by_user_id,
        )
        return ExecutorResult(record_refs={"run_id": str(row.id), "status": row.status})


class AddTransferPricingTransactionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.transfer_pricing.service import add_transaction

        payload = dict(intent.payload_json or {})
        row = await add_transaction(
            db,
            tenant_id=intent.tenant_id,
            fiscal_year=int(payload["fiscal_year"]),
            transaction_type=str(payload["transaction_type"]),
            related_party_name=str(payload["related_party_name"]),
            related_party_country=str(payload["related_party_country"]),
            transaction_amount=Decimal(str(payload["transaction_amount"])),
            currency=str(payload.get("currency") or "INR"),
            pricing_method=str(payload["pricing_method"]),
            is_international=bool(payload.get("is_international", True)),
            arm_length_price=Decimal(str(payload["arm_length_price"])) if payload.get("arm_length_price") not in {None, ""} else None,
            actual_price=Decimal(str(payload["actual_price"])) if payload.get("actual_price") not in {None, ""} else None,
            description=str(payload["description"]) if payload.get("description") not in {None, ""} else None,
        )
        return ExecutorResult(record_refs={"transaction_id": str(row.id)})


class GenerateTransferPricingDocExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.transfer_pricing.service import generate_form_3ceb

        payload = dict(intent.payload_json or {})
        row = await generate_form_3ceb(
            db,
            tenant_id=intent.tenant_id,
            fiscal_year=int(payload["fiscal_year"]),
            created_by=intent.requested_by_user_id,
        )
        return ExecutorResult(record_refs={"document_id": str(row.id), "status": row.status})


class EnsureMultiGaapConfigExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.multi_gaap.service import get_or_create_config

        payload = dict(intent.payload_json or {})
        row = await get_or_create_config(
            db,
            tenant_id=intent.tenant_id,
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(record_refs={"config_id": str(row.id)})


class UpdateMultiGaapConfigExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.multi_gaap.service import update_config

        payload = dict(intent.payload_json or {})
        row = await update_config(
            db,
            tenant_id=intent.tenant_id,
            updates=dict(payload.get("updates") or {}),
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(record_refs={"config_id": str(row.id)})


class ComputeMultiGaapViewExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.multi_gaap.service import compute_gaap_view

        payload = dict(intent.payload_json or {})
        row = await compute_gaap_view(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            gaap_framework=str(payload["gaap_framework"]),
            created_by=intent.requested_by_user_id,
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(record_refs={"run_id": str(row.id)})


class EnsureStatutoryFilingsExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.statutory.service import ensure_standard_filings

        payload = dict(intent.payload_json or {})
        await ensure_standard_filings(
            db,
            tenant_id=intent.tenant_id,
            entity_id=_optional_uuid_value(payload, "entity_id"),
            fiscal_year=int(payload["fiscal_year"]),
        )
        return ExecutorResult(
            record_refs={
                "entity_id": str(payload["entity_id"]) if payload.get("entity_id") else None,
                "fiscal_year": int(payload["fiscal_year"]),
            }
        )


class MarkStatutoryFilingExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.statutory.service import mark_as_filed

        payload = dict(intent.payload_json or {})
        row = await mark_as_filed(
            db,
            tenant_id=intent.tenant_id,
            filing_id=_uuid_value(payload, "filing_id"),
            filed_date=date.fromisoformat(str(payload["filed_date"])),
            filing_reference=str(payload["filing_reference"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(record_refs={"filing_id": str(row.id)})


class AddStatutoryRegisterEntryExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.statutory.service import add_register_entry

        payload = dict(intent.payload_json or {})
        row = await add_register_entry(
            db,
            tenant_id=intent.tenant_id,
            register_type=str(payload["register_type"]),
            entry_date=date.fromisoformat(str(payload["entry_date"])),
            entry_description=str(payload["entry_description"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
            folio_number=str(payload["folio_number"]) if payload.get("folio_number") not in {None, ""} else None,
            amount=Decimal(str(payload["amount"])) if payload.get("amount") not in {None, ""} else None,
            currency=str(payload["currency"]) if payload.get("currency") not in {None, ""} else None,
            reference_document=str(payload["reference_document"]) if payload.get("reference_document") not in {None, ""} else None,
        )
        return ExecutorResult(record_refs={"entry_id": str(row.id)})


class EnsureExpensePolicyExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.expense_management.service import _get_or_create_policy

        row = await _get_or_create_policy(db, intent.tenant_id)
        return ExecutorResult(record_refs={"policy_id": str(row.id)})


class SubmitExpenseClaimExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.expense_management.service import submit_claim

        payload = dict(intent.payload_json or {})
        row = await submit_claim(
            db,
            tenant_id=intent.tenant_id,
            submitted_by=intent.requested_by_user_id,
            vendor_name=str(payload["vendor_name"]),
            description=str(payload["description"]),
            category=str(payload["category"]),
            amount=Decimal(str(payload["amount"])),
            currency=str(payload.get("currency") or "INR"),
            claim_date=date.fromisoformat(str(payload["claim_date"])),
            has_receipt=bool(payload["has_receipt"]),
            receipt_url=str(payload["receipt_url"]) if payload.get("receipt_url") not in {None, ""} else None,
            justification=str(payload["justification"]) if payload.get("justification") not in {None, ""} else None,
            location_id=_optional_uuid_value(payload, "location_id"),
            cost_centre_id=_optional_uuid_value(payload, "cost_centre_id"),
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(record_refs={"claim_id": str(row.id), "status": row.status})


class UpdateExpensePolicyExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.expense_management.service import update_policy

        payload = dict(intent.payload_json or {})
        updates = dict(payload.get("updates") or {})
        decimal_fields = {
            "meal_limit_per_day",
            "travel_limit_per_night",
            "receipt_required_above",
            "auto_approve_below",
        }
        normalized = {
            key: (Decimal(str(value)) if key in decimal_fields and value is not None else value)
            for key, value in updates.items()
        }
        row = await update_policy(
            db,
            tenant_id=intent.tenant_id,
            updates=normalized,
        )
        return ExecutorResult(record_refs={"policy_id": str(row.id)})


class ApproveExpenseClaimExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.expense_management.service import approve_claim

        payload = dict(intent.payload_json or {})
        result = await approve_claim(
            db,
            tenant_id=intent.tenant_id,
            claim_id=_uuid_value(payload, "claim_id"),
            approver_id=intent.requested_by_user_id,
            approver_role=str(intent.requested_by_role or ""),
            action=str(payload["action"]),
            comments=str(payload["comments"]) if payload.get("comments") not in {None, ""} else None,
        )
        return ExecutorResult(record_refs=result)


class CreateCovenantDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.debt_covenants.service import create_covenant_definition

        payload = dict(intent.payload_json or {})
        row = await create_covenant_definition(
            db,
            tenant_id=intent.tenant_id,
            entity_id=_uuid_value(payload, "entity_id"),
            facility_name=str(payload["facility_name"]),
            lender_name=str(payload["lender_name"]),
            covenant_type=str(payload["covenant_type"]),
            covenant_label=str(payload["covenant_label"]),
            threshold_value=Decimal(str(payload["threshold_value"])),
            threshold_direction=str(payload["threshold_direction"]),
            measurement_frequency=str(payload.get("measurement_frequency") or "monthly"),
            grace_period_days=int(payload.get("grace_period_days") or 0),
            notification_threshold_pct=Decimal(str(payload.get("notification_threshold_pct") or "90.00")),
        )
        return ExecutorResult(record_refs={"covenant_id": str(row.id)})


class UpdateCovenantDefinitionExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.debt_covenants.service import update_covenant_definition

        payload = dict(intent.payload_json or {})
        covenant_id = intent.target_id or _uuid_value(payload, "covenant_id")
        updates = dict(payload.get("updates") or {})
        if "threshold_value" in updates and updates["threshold_value"] is not None:
            updates["threshold_value"] = Decimal(str(updates["threshold_value"]))
        if "notification_threshold_pct" in updates and updates["notification_threshold_pct"] is not None:
            updates["notification_threshold_pct"] = Decimal(str(updates["notification_threshold_pct"]))
        row = await update_covenant_definition(
            db,
            tenant_id=intent.tenant_id,
            covenant_id=covenant_id,
            updates=updates,
        )
        return ExecutorResult(record_refs={"covenant_id": str(row.id)})


class CheckCovenantsExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.modules.debt_covenants.service import check_all_covenants

        payload = dict(intent.payload_json or {})
        rows = await check_all_covenants(
            db,
            tenant_id=intent.tenant_id,
            period=str(payload["period"]),
            entity_id=_optional_uuid_value(payload, "entity_id"),
        )
        return ExecutorResult(
            record_refs={
                "event_ids": [str(row.id) for row in rows],
                "count": len(rows),
            }
        )


class BatchMutationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from financeops.core.intent.service import IntentActor, IntentService

        payload = dict(intent.payload_json or {})
        items = list(payload.get("items") or [])
        actor = IntentActor(
            user_id=intent.requested_by_user_id,
            tenant_id=intent.tenant_id,
            role=intent.requested_by_role,
            source_channel=intent.source_channel,
        )
        service = IntentService(db)
        child_results: list[dict[str, Any]] = []
        failed_items: list[dict[str, Any]] = []

        for index, item in enumerate(items):
            item_payload = dict(item.get("payload") or {})
            item_type = IntentType(str(item["intent_type"]))
            item_target_id = (
                uuid.UUID(str(item["target_id"])) if item.get("target_id") not in {None, ""} else None
            )
            item_key = str(item.get("idempotency_key") or f"{intent.idempotency_key}:{index}")
            try:
                child = await service.submit_intent(
                    intent_type=item_type,
                    actor=actor,
                    payload=item_payload,
                    idempotency_key=item_key,
                    target_id=item_target_id,
                    parent_intent_id=intent.id,
                )
                child_results.append(
                    {
                        "index": index,
                        "intent_id": str(child.intent_id),
                        "job_id": str(child.job_id) if child.job_id else None,
                        "status": child.status,
                        "next_action": child.next_action,
                        "record_refs": child.record_refs,
                    }
                )
            except Exception as exc:
                failed_items.append(
                    {
                        "index": index,
                        "intent_type": item_type.value,
                        "payload": item_payload,
                        "target_id": str(item_target_id) if item_target_id else None,
                        "error": str(exc),
                        "idempotency_key": item_key,
                    }
                )

        return ExecutorResult(
            record_refs={
                "batch_intent_id": str(intent.id),
                "child_results": child_results,
                "failed_items": failed_items,
                "success_count": len(child_results),
                "failed_count": len(failed_items),
            },
            final_status=IntentStatus.PARTIAL_SUCCESS.value if failed_items else IntentStatus.RECORDED.value,
        )


class RetryBatchMutationExecutor(BaseIntentExecutor):
    async def execute(self, db: AsyncSession, *, intent: CanonicalIntent) -> ExecutorResult:
        from sqlalchemy import select

        from financeops.core.intent.service import IntentActor, IntentService
        from financeops.db.models.intent_pipeline import CanonicalIntent as CanonicalIntentModel

        payload = dict(intent.payload_json or {})
        parent_id = uuid.UUID(str(payload["parent_intent_id"]))
        parent = (
            await db.execute(
                select(CanonicalIntentModel).where(
                    CanonicalIntentModel.tenant_id == intent.tenant_id,
                    CanonicalIntentModel.id == parent_id,
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise ValidationError("Batch parent intent not found.")

        failed_items = list((parent.record_refs_json or {}).get("failed_items") or [])
        actor = IntentActor(
            user_id=intent.requested_by_user_id,
            tenant_id=intent.tenant_id,
            role=intent.requested_by_role,
            source_channel=intent.source_channel,
        )
        service = IntentService(db)
        child_results: list[dict[str, Any]] = []
        remaining_failures: list[dict[str, Any]] = []

        for index, item in enumerate(failed_items):
            item_payload = dict(item.get("payload") or {})
            item_type = IntentType(str(item["intent_type"]))
            item_target_id = (
                uuid.UUID(str(item["target_id"])) if item.get("target_id") not in {None, ""} else None
            )
            retry_key = f"{intent.idempotency_key}:{index}"
            try:
                child = await service.submit_intent(
                    intent_type=item_type,
                    actor=actor,
                    payload=item_payload,
                    idempotency_key=retry_key,
                    target_id=item_target_id,
                    parent_intent_id=intent.id,
                )
                child_results.append(
                    {
                        "index": index,
                        "intent_id": str(child.intent_id),
                        "job_id": str(child.job_id) if child.job_id else None,
                        "status": child.status,
                        "next_action": child.next_action,
                        "record_refs": child.record_refs,
                    }
                )
            except Exception as exc:
                remaining_failures.append(
                    {
                        **item,
                        "error": str(exc),
                        "idempotency_key": retry_key,
                    }
                )

        return ExecutorResult(
            record_refs={
                "batch_intent_id": str(intent.id),
                "retried_parent_intent_id": str(parent.id),
                "child_results": child_results,
                "failed_items": remaining_failures,
                "success_count": len(child_results),
                "failed_count": len(remaining_failures),
            },
            final_status=IntentStatus.PARTIAL_SUCCESS.value if remaining_failures else IntentStatus.RECORDED.value,
        )


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
            IntentType.IMPORT_BANK_STATEMENT.value: ImportBankStatementExecutor(),
            IntentType.CREATE_BANK_STATEMENT.value: CreateBankStatementExecutor(),
            IntentType.ADD_BANK_TRANSACTION.value: AddBankTransactionExecutor(),
            IntentType.RUN_BANK_RECONCILIATION.value: RunBankReconciliationExecutor(),
            IntentType.PREPARE_GST_RETURN.value: PrepareGstReturnExecutor(),
            IntentType.SUBMIT_GST_RETURN.value: SubmitGstReturnExecutor(),
            IntentType.RUN_GST_RECONCILIATION.value: RunGstReconciliationExecutor(),
            IntentType.CREATE_FIXED_ASSET_CLASS.value: CreateFixedAssetClassExecutor(),
            IntentType.UPDATE_FIXED_ASSET_CLASS.value: UpdateFixedAssetClassExecutor(),
            IntentType.CREATE_FIXED_ASSET.value: CreateFixedAssetExecutor(),
            IntentType.UPDATE_FIXED_ASSET.value: UpdateFixedAssetExecutor(),
            IntentType.RUN_FIXED_ASSET_DEPRECIATION.value: RunFixedAssetDepreciationExecutor(),
            IntentType.RUN_FIXED_ASSET_WORKFLOW.value: RunFixedAssetWorkflowExecutor(),
            IntentType.POST_FIXED_ASSET_REVALUATION.value: PostFixedAssetRevaluationExecutor(),
            IntentType.POST_FIXED_ASSET_IMPAIRMENT.value: PostFixedAssetImpairmentExecutor(),
            IntentType.DISPOSE_FIXED_ASSET.value: DisposeFixedAssetExecutor(),
            IntentType.CREATE_PREPAID_SCHEDULE.value: CreatePrepaidScheduleExecutor(),
            IntentType.UPDATE_PREPAID_SCHEDULE.value: UpdatePrepaidScheduleExecutor(),
            IntentType.POST_PREPAID_AMORTIZATION.value: PostPrepaidAmortizationExecutor(),
            IntentType.RUN_PREPAID_WORKFLOW.value: RunPrepaidWorkflowExecutor(),
            IntentType.START_LEGACY_CONSOLIDATION_RUN.value: StartLegacyConsolidationRunExecutor(),
            IntentType.RUN_CONSOLIDATION.value: RunConsolidationExecutor(),
            IntentType.EXECUTE_CONSOLIDATION.value: ExecuteConsolidationExecutor(),
            IntentType.CREATE_REPORT_DEFINITION.value: CreateReportDefinitionExecutor(),
            IntentType.UPDATE_REPORT_DEFINITION.value: UpdateReportDefinitionExecutor(),
            IntentType.DEACTIVATE_REPORT_DEFINITION.value: DeactivateReportDefinitionExecutor(),
            IntentType.GENERATE_REPORT.value: GenerateReportExecutor(),
            IntentType.CREATE_BOARD_PACK_DEFINITION.value: CreateBoardPackDefinitionExecutor(),
            IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION.value: CreateBoardPackNarrativeDefinitionExecutor(),
            IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION.value: CreateBoardPackSectionDefinitionExecutor(),
            IntentType.CREATE_NARRATIVE_TEMPLATE.value: CreateNarrativeTemplateExecutor(),
            IntentType.CREATE_BOARD_PACK_INCLUSION_RULE.value: CreateBoardPackInclusionRuleExecutor(),
            IntentType.CREATE_BOARD_PACK_NARRATIVE_RUN.value: CreateBoardPackNarrativeRunExecutor(),
            IntentType.EXECUTE_BOARD_PACK_NARRATIVE_RUN.value: ExecuteBoardPackNarrativeRunExecutor(),
            IntentType.UPDATE_BOARD_PACK_DEFINITION.value: UpdateBoardPackDefinitionExecutor(),
            IntentType.DEACTIVATE_BOARD_PACK_DEFINITION.value: DeactivateBoardPackDefinitionExecutor(),
            IntentType.GENERATE_BOARD_PACK.value: GenerateBoardPackExecutor(),
            IntentType.CREATE_WORKING_CAPITAL_SNAPSHOT.value: CreateWorkingCapitalSnapshotExecutor(),
            IntentType.CREATE_BUDGET_VERSION.value: CreateBudgetVersionExecutor(),
            IntentType.UPSERT_BUDGET_LINE.value: UpsertBudgetLineExecutor(),
            IntentType.SUBMIT_BUDGET_VERSION.value: SubmitBudgetVersionExecutor(),
            IntentType.APPROVE_BUDGET_VERSION.value: ApproveBudgetVersionExecutor(),
            IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT.value: ComputeWorkingCapitalSnapshotExecutor(),
            IntentType.CREATE_CHECKLIST_TEMPLATE.value: CreateChecklistTemplateExecutor(),
            IntentType.ENSURE_CHECKLIST_RUN.value: EnsureChecklistRunExecutor(),
            IntentType.UPDATE_CHECKLIST_TASK_STATUS.value: UpdateChecklistTaskStatusExecutor(),
            IntentType.ASSIGN_CHECKLIST_TASK.value: AssignChecklistTaskExecutor(),
            IntentType.AUTO_COMPLETE_CHECKLIST_TASKS.value: AutoCompleteChecklistTasksExecutor(),
            IntentType.CREATE_MONTHEND_CHECKLIST.value: CreateMonthendChecklistExecutor(),
            IntentType.ADD_MONTHEND_TASK.value: AddMonthendTaskExecutor(),
            IntentType.UPDATE_MONTHEND_TASK_STATUS.value: UpdateMonthendTaskStatusExecutor(),
            IntentType.CLOSE_MONTHEND_CHECKLIST.value: CloseMonthendChecklistExecutor(),
            IntentType.CREATE_FORECAST_RUN.value: CreateForecastRunExecutor(),
            IntentType.UPDATE_FORECAST_ASSUMPTION.value: UpdateForecastAssumptionExecutor(),
            IntentType.COMPUTE_FORECAST_LINES.value: ComputeForecastLinesExecutor(),
            IntentType.PUBLISH_FORECAST.value: PublishForecastExecutor(),
            IntentType.COMPUTE_TAX_PROVISION.value: ComputeTaxProvisionExecutor(),
            IntentType.UPSERT_TAX_POSITION.value: UpsertTaxPositionExecutor(),
            IntentType.CREATE_CASH_FLOW_FORECAST.value: CreateCashFlowForecastExecutor(),
            IntentType.UPDATE_CASH_FLOW_WEEK.value: UpdateCashFlowWeekExecutor(),
            IntentType.PUBLISH_CASH_FLOW_FORECAST.value: PublishCashFlowForecastExecutor(),
            IntentType.ADD_TRANSFER_PRICING_TRANSACTION.value: AddTransferPricingTransactionExecutor(),
            IntentType.GENERATE_TRANSFER_PRICING_DOC.value: GenerateTransferPricingDocExecutor(),
            IntentType.ENSURE_MULTI_GAAP_CONFIG.value: EnsureMultiGaapConfigExecutor(),
            IntentType.UPDATE_MULTI_GAAP_CONFIG.value: UpdateMultiGaapConfigExecutor(),
            IntentType.COMPUTE_MULTI_GAAP_VIEW.value: ComputeMultiGaapViewExecutor(),
            IntentType.ENSURE_STATUTORY_FILINGS.value: EnsureStatutoryFilingsExecutor(),
            IntentType.MARK_STATUTORY_FILING.value: MarkStatutoryFilingExecutor(),
            IntentType.ADD_STATUTORY_REGISTER_ENTRY.value: AddStatutoryRegisterEntryExecutor(),
            IntentType.ENSURE_EXPENSE_POLICY.value: EnsureExpensePolicyExecutor(),
            IntentType.SUBMIT_EXPENSE_CLAIM.value: SubmitExpenseClaimExecutor(),
            IntentType.UPDATE_EXPENSE_POLICY.value: UpdateExpensePolicyExecutor(),
            IntentType.APPROVE_EXPENSE_CLAIM.value: ApproveExpenseClaimExecutor(),
            IntentType.CREATE_COVENANT_DEFINITION.value: CreateCovenantDefinitionExecutor(),
            IntentType.UPDATE_COVENANT_DEFINITION.value: UpdateCovenantDefinitionExecutor(),
            IntentType.CHECK_COVENANTS.value: CheckCovenantsExecutor(),
            IntentType.BATCH_MUTATION.value: BatchMutationExecutor(),
            IntentType.RETRY_BATCH_MUTATION.value: RetryBatchMutationExecutor(),
        }

    def resolve(self, intent_type: str) -> BaseIntentExecutor:
        executor = self._executors.get(intent_type)
        if executor is None:
            raise ValidationError(f"No executor is registered for intent type '{intent_type}'.")
        return executor
