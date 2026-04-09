from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.approvals import ApprovalResolver
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.core.intent.enums import (
    IntentEventType,
    IntentType,
    JobStatus,
    IntentStatus,
    NextAction,
)
from financeops.core.intent.guards import IntentGuardAdapter
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalIntentEvent
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _intent_metadata(intent_type: IntentType, *, has_target: bool) -> tuple[str, str]:
    metadata: dict[IntentType, tuple[str, str]] = {
        IntentType.CREATE_JOURNAL: ("accounting_layer", "journal_request"),
        IntentType.SUBMIT_JOURNAL: ("accounting_layer", "journal"),
        IntentType.REVIEW_JOURNAL: ("accounting_layer", "journal"),
        IntentType.APPROVE_JOURNAL: ("accounting_layer", "journal"),
        IntentType.POST_JOURNAL: ("accounting_layer", "journal"),
        IntentType.REVERSE_JOURNAL: ("accounting_layer", "journal"),
        IntentType.CREATE_ERP_SYNC_RUN: ("erp_sync", "sync_run_request"),
        IntentType.CREATE_NORMALIZATION_RUN: ("normalization", "normalization_run_request"),
        IntentType.IMPORT_BANK_STATEMENT: ("bank_reconciliation", "bank_statement_import"),
        IntentType.CREATE_BANK_STATEMENT: ("bank_reconciliation", "bank_statement"),
        IntentType.ADD_BANK_TRANSACTION: ("bank_reconciliation", "bank_transaction"),
        IntentType.RUN_BANK_RECONCILIATION: ("bank_reconciliation", "bank_reconciliation_run"),
        IntentType.PREPARE_GST_RETURN: ("gst", "gst_return"),
        IntentType.SUBMIT_GST_RETURN: ("gst", "gst_return"),
        IntentType.RUN_GST_RECONCILIATION: ("gst", "gst_reconciliation_run"),
        IntentType.CREATE_FIXED_ASSET_CLASS: ("fixed_assets", "fixed_asset_class"),
        IntentType.UPDATE_FIXED_ASSET_CLASS: ("fixed_assets", "fixed_asset_class"),
        IntentType.CREATE_FIXED_ASSET: ("fixed_assets", "fixed_asset"),
        IntentType.UPDATE_FIXED_ASSET: ("fixed_assets", "fixed_asset"),
        IntentType.RUN_FIXED_ASSET_DEPRECIATION: ("fixed_assets", "fixed_asset_depreciation"),
        IntentType.RUN_FIXED_ASSET_WORKFLOW: ("fixed_assets", "far_run"),
        IntentType.POST_FIXED_ASSET_REVALUATION: ("fixed_assets", "fixed_asset_revaluation"),
        IntentType.POST_FIXED_ASSET_IMPAIRMENT: ("fixed_assets", "fixed_asset_impairment"),
        IntentType.DISPOSE_FIXED_ASSET: ("fixed_assets", "fixed_asset"),
        IntentType.CREATE_PREPAID_SCHEDULE: ("prepaid", "prepaid_schedule"),
        IntentType.UPDATE_PREPAID_SCHEDULE: ("prepaid", "prepaid_schedule"),
        IntentType.POST_PREPAID_AMORTIZATION: ("prepaid", "prepaid_amortization_run"),
        IntentType.RUN_PREPAID_WORKFLOW: ("prepaid", "prepaid_run"),
        IntentType.RUN_CONSOLIDATION: ("multi_entity_consolidation", "consolidation_run"),
        IntentType.EXECUTE_CONSOLIDATION: ("multi_entity_consolidation", "consolidation_run"),
        IntentType.CREATE_REPORT_DEFINITION: ("custom_report_builder", "report_definition"),
        IntentType.UPDATE_REPORT_DEFINITION: ("custom_report_builder", "report_definition"),
        IntentType.DEACTIVATE_REPORT_DEFINITION: ("custom_report_builder", "report_definition"),
        IntentType.GENERATE_REPORT: ("custom_report_builder", "report_run"),
        IntentType.CREATE_BOARD_PACK_DEFINITION: ("board_pack_generator", "board_pack_definition"),
        IntentType.UPDATE_BOARD_PACK_DEFINITION: ("board_pack_generator", "board_pack_definition"),
        IntentType.DEACTIVATE_BOARD_PACK_DEFINITION: ("board_pack_generator", "board_pack_definition"),
        IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION: ("board_pack_narrative_engine", "board_pack_definition"),
        IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION: ("board_pack_narrative_engine", "board_pack_section_definition"),
        IntentType.CREATE_NARRATIVE_TEMPLATE: ("board_pack_narrative_engine", "narrative_template"),
        IntentType.CREATE_BOARD_PACK_INCLUSION_RULE: ("board_pack_narrative_engine", "board_pack_inclusion_rule"),
        IntentType.CREATE_BOARD_PACK_NARRATIVE_RUN: ("board_pack_narrative_engine", "board_pack_run"),
        IntentType.EXECUTE_BOARD_PACK_NARRATIVE_RUN: ("board_pack_narrative_engine", "board_pack_run"),
        IntentType.GENERATE_BOARD_PACK: ("board_pack_generator", "board_pack_run"),
        IntentType.START_LEGACY_CONSOLIDATION_RUN: ("consolidation", "consolidation_run"),
        IntentType.CREATE_WORKING_CAPITAL_SNAPSHOT: ("working_capital", "working_capital_snapshot"),
        IntentType.CREATE_BUDGET_VERSION: ("budgeting", "budget_version"),
        IntentType.UPSERT_BUDGET_LINE: ("budgeting", "budget_line"),
        IntentType.APPROVE_BUDGET_VERSION: ("budgeting", "budget_version"),
        IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT: ("working_capital_analysis", "working_capital_snapshot"),
        IntentType.CREATE_CHECKLIST_TEMPLATE: ("closing_checklist", "checklist_template"),
        IntentType.ENSURE_CHECKLIST_RUN: ("closing_checklist", "checklist_run"),
        IntentType.UPDATE_CHECKLIST_TASK_STATUS: ("closing_checklist", "checklist_task"),
        IntentType.ASSIGN_CHECKLIST_TASK: ("closing_checklist", "checklist_task"),
        IntentType.AUTO_COMPLETE_CHECKLIST_TASKS: ("closing_checklist", "checklist_run"),
        IntentType.CREATE_MONTHEND_CHECKLIST: ("monthend", "monthend_checklist"),
        IntentType.ADD_MONTHEND_TASK: ("monthend", "monthend_task"),
        IntentType.UPDATE_MONTHEND_TASK_STATUS: ("monthend", "monthend_task"),
        IntentType.CLOSE_MONTHEND_CHECKLIST: ("monthend", "monthend_checklist"),
        IntentType.CREATE_FORECAST_RUN: ("forecasting", "forecast_run"),
        IntentType.UPDATE_FORECAST_ASSUMPTION: ("forecasting", "forecast_assumption"),
        IntentType.COMPUTE_FORECAST_LINES: ("forecasting", "forecast_run"),
        IntentType.PUBLISH_FORECAST: ("forecasting", "forecast_run"),
        IntentType.CREATE_CASH_FLOW_FORECAST: ("cash_flow_forecast", "cash_flow_forecast_run"),
        IntentType.UPDATE_CASH_FLOW_WEEK: ("cash_flow_forecast", "cash_flow_forecast_week"),
        IntentType.PUBLISH_CASH_FLOW_FORECAST: ("cash_flow_forecast", "cash_flow_forecast_run"),
        IntentType.COMPUTE_TAX_PROVISION: ("tax_provision", "tax_provision_run"),
        IntentType.UPSERT_TAX_POSITION: ("tax_provision", "tax_position"),
        IntentType.ADD_TRANSFER_PRICING_TRANSACTION: ("transfer_pricing", "intercompany_transaction"),
        IntentType.GENERATE_TRANSFER_PRICING_DOC: ("transfer_pricing", "transfer_pricing_document"),
        IntentType.ENSURE_EXPENSE_POLICY: ("expense_management", "expense_policy"),
        IntentType.SUBMIT_EXPENSE_CLAIM: ("expense_management", "expense_claim"),
        IntentType.UPDATE_EXPENSE_POLICY: ("expense_management", "expense_policy"),
        IntentType.APPROVE_EXPENSE_CLAIM: ("expense_management", "expense_claim"),
        IntentType.ENSURE_MULTI_GAAP_CONFIG: ("multi_gaap", "multi_gaap_config"),
        IntentType.UPDATE_MULTI_GAAP_CONFIG: ("multi_gaap", "multi_gaap_config"),
        IntentType.COMPUTE_MULTI_GAAP_VIEW: ("multi_gaap", "multi_gaap_run"),
        IntentType.ENSURE_STATUTORY_FILINGS: ("statutory", "statutory_filing_calendar"),
        IntentType.MARK_STATUTORY_FILING: ("statutory", "statutory_filing"),
        IntentType.ADD_STATUTORY_REGISTER_ENTRY: ("statutory", "statutory_register_entry"),
        IntentType.CREATE_COVENANT_DEFINITION: ("debt_covenants", "covenant_definition"),
        IntentType.UPDATE_COVENANT_DEFINITION: ("debt_covenants", "covenant_definition"),
        IntentType.CHECK_COVENANTS: ("debt_covenants", "covenant_check_run"),
        IntentType.BATCH_MUTATION: ("control_plane", "batch_intent"),
        IntentType.RETRY_BATCH_MUTATION: ("control_plane", "batch_intent"),
    }
    if intent_type in metadata:
        module_key, target_type = metadata[intent_type]
        if has_target and intent_type == IntentType.CREATE_JOURNAL:
            return module_key, "journal"
        return module_key, target_type
    return "accounting_layer", "journal" if has_target else "journal_request"


@dataclass(frozen=True)
class IntentActor:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    source_channel: str
    request_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class IntentSubmissionResult:
    intent_id: uuid.UUID
    status: str
    job_id: uuid.UUID | None
    next_action: str
    record_refs: dict[str, Any] | None


class IntentService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        guard_engine: IntentGuardAdapter | None = None,
        approval_resolver: ApprovalResolver | None = None,
        dispatcher: JobDispatcher | None = None,
    ) -> None:
        self._db = db
        self._guards = guard_engine or IntentGuardAdapter()
        self._approvals = approval_resolver or ApprovalResolver()
        self._dispatcher = dispatcher or JobDispatcher()

    async def submit_intent(
        self,
        *,
        intent_type: IntentType,
        actor: IntentActor,
        payload: dict[str, Any] | None,
        idempotency_key: str,
        target_id: uuid.UUID | None = None,
        parent_intent_id: uuid.UUID | None = None,
    ) -> IntentSubmissionResult:
        intent = await self._find_existing_intent(
            tenant_id=actor.tenant_id,
            intent_type=intent_type.value,
            idempotency_key=idempotency_key,
            target_id=target_id,
        )
        if intent is not None:
            return IntentSubmissionResult(
                intent_id=intent.id,
                status=intent.status,
                job_id=intent.job_id,
                next_action=NextAction.NONE.value,
                record_refs=intent.record_refs_json,
            )

        entity = await self._resolve_entity(actor.tenant_id, intent_type, payload or {}, target_id)
        intent = await self.create_draft(
            intent_type=intent_type,
            payload=payload or {},
            actor=actor,
            entity=entity,
            target_id=target_id,
            idempotency_key=idempotency_key,
            parent_intent_id=parent_intent_id,
        )
        await self.submit_existing_intent(intent, actor=actor)
        await self.validate_intent(intent, actor=actor)

        resolution = await self._approvals.resolve(
            self._db,
            intent=intent,
            actor_role=actor.role,
        )
        intent.approval_policy_id = uuid.UUID(resolution.policy_id) if resolution.policy_id else None
        await self._db.flush()
        if resolution.approval_required and not resolution.is_granted:
            return IntentSubmissionResult(
                intent_id=intent.id,
                status=intent.status,
                job_id=None,
                next_action=resolution.next_action,
                record_refs=intent.record_refs_json,
            )

        await self.approve_intent(intent, actor=actor)
        job = await self.dispatch_intent(intent)
        return IntentSubmissionResult(
            intent_id=intent.id,
            status=intent.status,
            job_id=job.id,
            next_action=NextAction.NONE.value,
            record_refs=intent.record_refs_json,
        )

    async def create_draft(
        self,
        *,
        intent_type: IntentType,
        payload: dict[str, Any],
        actor: IntentActor,
        entity: CpEntity,
        target_id: uuid.UUID | None,
        idempotency_key: str,
        parent_intent_id: uuid.UUID | None = None,
    ) -> CanonicalIntent:
        intent = CanonicalIntent(
            id=uuid.uuid4(),
            intent_type=intent_type.value,
            tenant_id=actor.tenant_id,
            org_id=entity.organisation_id,
            entity_id=entity.id,
            module_key=_intent_metadata(intent_type, has_target=target_id is not None)[0],
            target_type=_intent_metadata(intent_type, has_target=target_id is not None)[1],
            target_id=target_id,
            parent_intent_id=parent_intent_id,
            status=IntentStatus.DRAFT.value,
            requested_by_user_id=actor.user_id,
            requested_by_role=actor.role,
            requested_at=_utcnow(),
            payload_json=payload,
            idempotency_key=idempotency_key,
            source_channel=actor.source_channel,
        )
        self._db.add(intent)
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.AUTH_CONTEXT_CAPTURED,
            payload={
                "request_id": actor.request_id,
                "correlation_id": actor.correlation_id,
                "source_channel": actor.source_channel,
            },
        )
        await self._emit_event(
            intent,
            event_type=IntentEventType.INTENT_CREATED,
            to_status=IntentStatus.DRAFT.value,
            payload={"intent_type": intent.intent_type},
        )
        return intent

    async def submit_existing_intent(
        self,
        intent: CanonicalIntent,
        *,
        actor: IntentActor,
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = IntentStatus.SUBMITTED.value
        intent.submitted_at = _utcnow()
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.INTENT_SUBMITTED,
            from_status=from_status,
            to_status=intent.status,
            payload={"submitted_by": str(actor.user_id)},
        )
        return intent

    async def validate_intent(
        self,
        intent: CanonicalIntent,
        *,
        actor: IntentActor | None = None,
    ) -> CanonicalIntent:
        evaluation = await self._guards.evaluate(
            self._db,
            intent=intent,
            actor_role=actor.role if actor is not None else intent.requested_by_role,
        )
        intent.guard_results_json = {
            "overall_passed": evaluation.overall_passed,
            "results": [
                {
                    "guard_code": result.guard_code,
                    "guard_name": result.guard_name,
                    "result": result.result.value,
                    "severity": result.severity,
                    "message": result.message,
                    "details": result.details,
                    "evaluated_at": result.evaluated_at.isoformat() if result.evaluated_at else None,
                }
                for result in evaluation.results
            ],
        }
        if not evaluation.overall_passed:
            failure_messages = "; ".join(result.message for result in evaluation.blocking_failures)
            await self.reject_intent(intent, actor=actor, reason=failure_messages)
            raise ValidationError(failure_messages)

        from_status = intent.status
        intent.status = IntentStatus.VALIDATED.value
        intent.validated_at = _utcnow()
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.INTENT_VALIDATED,
            from_status=from_status,
            to_status=intent.status,
            payload=intent.guard_results_json,
        )
        return intent

    async def approve_intent(
        self,
        intent: CanonicalIntent,
        *,
        actor: IntentActor,
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = IntentStatus.APPROVED.value
        intent.approved_at = _utcnow()
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.INTENT_APPROVED,
            from_status=from_status,
            to_status=intent.status,
            payload={"approved_by": str(actor.user_id)},
        )
        return intent

    async def reject_intent(
        self,
        intent: CanonicalIntent,
        *,
        actor: IntentActor | None,
        reason: str,
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = IntentStatus.REJECTED.value
        intent.rejected_at = _utcnow()
        intent.rejection_reason = reason
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.INTENT_REJECTED,
            from_status=from_status,
            to_status=intent.status,
            payload={"reason": reason, "actor": str(actor.user_id) if actor is not None else None},
        )
        return intent

    async def dispatch_intent(
        self,
        intent: CanonicalIntent,
    ):
        job = await self._dispatcher.create_job(self._db, intent=intent)
        intent.job_id = job.id
        from_status = intent.status
        intent.status = IntentStatus.EXECUTING.value
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.JOB_DISPATCHED,
            from_status=from_status,
            to_status=intent.status,
            payload={"job_id": str(job.id), "runner_type": job.runner_type},
        )

        try:
            execution_result = await self._dispatcher.execute(self._db, intent=intent, job=job)
        except Exception as exc:
            job.status = JobStatus.FAILED.value
            job.failed_at = _utcnow()
            job.error_code = exc.__class__.__name__
            job.error_message = str(exc)
            intent.status = IntentStatus.REJECTED.value
            intent.rejected_at = _utcnow()
            intent.rejection_reason = str(exc)
            intent.updated_at = _utcnow()
            await self._db.flush()
            raise
        await self.mark_executed(intent, job_id=job.id, result=execution_result.record_refs)
        await self.mark_recorded(
            intent,
            record_refs=execution_result.record_refs,
            final_status=execution_result.final_status,
        )
        return job

    async def mark_executed(
        self,
        intent: CanonicalIntent,
        *,
        job_id: uuid.UUID,
        result: dict[str, Any],
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = IntentStatus.EXECUTED.value
        intent.executed_at = _utcnow()
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.JOB_EXECUTED,
            from_status=from_status,
            to_status=intent.status,
            payload={"job_id": str(job_id), "result": result},
        )
        return intent

    async def mark_recorded(
        self,
        intent: CanonicalIntent,
        *,
        record_refs: dict[str, Any],
        final_status: str | None = None,
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = final_status or IntentStatus.RECORDED.value
        intent.recorded_at = _utcnow()
        intent.record_refs_json = record_refs
        intent.updated_at = _utcnow()
        await self._db.flush()
        await self._emit_event(
            intent,
            event_type=IntentEventType.RECORD_RECORDED,
            from_status=from_status,
            to_status=intent.status,
            payload=record_refs,
        )
        return intent

    async def retry_batch_intent(
        self,
        *,
        parent_intent_id: uuid.UUID,
        actor: IntentActor,
        idempotency_key: str,
    ) -> IntentSubmissionResult:
        payload = {"parent_intent_id": str(parent_intent_id)}
        return await self.submit_intent(
            intent_type=IntentType.RETRY_BATCH_MUTATION,
            actor=actor,
            payload=payload,
            idempotency_key=idempotency_key,
            parent_intent_id=parent_intent_id,
        )

    async def _find_existing_intent(
        self,
        *,
        tenant_id: uuid.UUID,
        intent_type: str,
        idempotency_key: str,
        target_id: uuid.UUID | None,
    ) -> CanonicalIntent | None:
        stmt = select(CanonicalIntent).where(
            CanonicalIntent.tenant_id == tenant_id,
            CanonicalIntent.intent_type == intent_type,
            CanonicalIntent.idempotency_key == idempotency_key,
        )
        if target_id is None:
            stmt = stmt.where(CanonicalIntent.target_id.is_(None))
        else:
            stmt = stmt.where(CanonicalIntent.target_id == target_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_entity(
        self,
        tenant_id: uuid.UUID,
        intent_type: IntentType,
        payload: dict[str, Any],
        target_id: uuid.UUID | None,
    ) -> CpEntity:
        entity_id = payload.get("org_entity_id") if intent_type == IntentType.CREATE_JOURNAL else payload.get("entity_id")
        if entity_id is None and isinstance(payload.get("entity_ids"), list) and payload["entity_ids"]:
            entity_id = payload["entity_ids"][0]
        if entity_id is not None:
            stmt = select(CpEntity).where(
                CpEntity.id == uuid.UUID(str(entity_id)),
                CpEntity.tenant_id == tenant_id,
            )
            result = await self._db.execute(stmt)
            entity = result.scalar_one_or_none()
            if entity is None:
                if intent_type not in {
                    IntentType.CREATE_REPORT_DEFINITION,
                    IntentType.UPDATE_REPORT_DEFINITION,
                    IntentType.DEACTIVATE_REPORT_DEFINITION,
                    IntentType.CREATE_BOARD_PACK_DEFINITION,
                    IntentType.UPDATE_BOARD_PACK_DEFINITION,
                    IntentType.DEACTIVATE_BOARD_PACK_DEFINITION,
                    IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION,
                    IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION,
                    IntentType.CREATE_NARRATIVE_TEMPLATE,
                    IntentType.CREATE_BOARD_PACK_INCLUSION_RULE,
                    IntentType.BATCH_MUTATION,
                    IntentType.RETRY_BATCH_MUTATION,
                }:
                    raise ValidationError("Entity does not belong to tenant.")
            else:
                return entity

        if intent_type == IntentType.CREATE_JOURNAL:
            raise ValidationError("org_entity_id is required.")

        if target_id is None:
            stmt = select(CpEntity).where(
                CpEntity.tenant_id == tenant_id,
            ).order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
            result = await self._db.execute(stmt)
            entity = result.scalars().first()
            if entity is None:
                raise ValidationError("Entity is required for governed intent scope.")
            return entity
        stmt = (
            select(CpEntity)
            .join(AccountingJVAggregate, AccountingJVAggregate.entity_id == CpEntity.id)
            .where(
                AccountingJVAggregate.id == target_id,
                AccountingJVAggregate.tenant_id == tenant_id,
                CpEntity.tenant_id == tenant_id,
            )
        )
        result = await self._db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is not None:
            return entity

        stmt = select(CpEntity).where(
            CpEntity.tenant_id == tenant_id,
        ).order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        result = await self._db.execute(stmt)
        entity = result.scalars().first()
        if entity is None:
            raise ValidationError("Entity is required for governed intent scope.")
        return entity

    async def _emit_event(
        self,
        intent: CanonicalIntent,
        *,
        event_type: IntentEventType,
        from_status: str | None = None,
        to_status: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CanonicalIntentEvent:
        event_payload = payload or {}
        return await AuditWriter.insert_financial_record(
            self._db,
            model_class=CanonicalIntentEvent,
            tenant_id=intent.tenant_id,
            record_data={
                "intent_id": str(intent.id),
                "event_type": event_type.value,
                "from_status": from_status or "",
                "to_status": to_status or "",
                "event_payload_json": event_payload,
            },
            values={
                "id": uuid.uuid4(),
                "intent_id": intent.id,
                "event_type": event_type.value,
                "from_status": from_status,
                "to_status": to_status,
                "actor_user_id": intent.requested_by_user_id,
                "actor_role": intent.requested_by_role,
                "event_at": _utcnow(),
                "event_payload_json": event_payload,
            },
            audit=AuditEvent(
                tenant_id=intent.tenant_id,
                action=event_type.value.lower(),
                resource_type="intent",
                user_id=intent.requested_by_user_id,
                resource_id=str(intent.id),
                new_value=event_payload,
            ),
        )
