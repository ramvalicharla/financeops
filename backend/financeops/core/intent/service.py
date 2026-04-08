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
from financeops.core.intent.guards import GuardEngine
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalIntentEvent
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _intent_metadata(intent_type: IntentType, *, has_target: bool) -> tuple[str, str]:
    if intent_type == IntentType.CREATE_ERP_SYNC_RUN:
        return "erp_sync", "sync_run_request"
    if intent_type == IntentType.CREATE_NORMALIZATION_RUN:
        return "normalization", "normalization_run_request"
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
        guard_engine: GuardEngine | None = None,
        approval_resolver: ApprovalResolver | None = None,
        dispatcher: JobDispatcher | None = None,
    ) -> None:
        self._db = db
        self._guards = guard_engine or GuardEngine()
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
            record_refs = await self._dispatcher.execute(self._db, intent=intent, job=job)
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
        await self.mark_executed(intent, job_id=job.id, result=record_refs)
        await self.mark_recorded(intent, record_refs=record_refs)
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
    ) -> CanonicalIntent:
        from_status = intent.status
        intent.status = IntentStatus.RECORDED.value
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
        if intent_type in {
            IntentType.CREATE_JOURNAL,
            IntentType.CREATE_ERP_SYNC_RUN,
            IntentType.CREATE_NORMALIZATION_RUN,
        }:
            entity_key = "org_entity_id" if intent_type == IntentType.CREATE_JOURNAL else "entity_id"
            entity_id = payload.get(entity_key)
            if entity_id is not None:
                stmt = select(CpEntity).where(
                    CpEntity.id == uuid.UUID(str(entity_id)),
                    CpEntity.tenant_id == tenant_id,
                )
                result = await self._db.execute(stmt)
                entity = result.scalar_one_or_none()
                if entity is None:
                    raise ValidationError("Entity does not belong to tenant.")
                return entity

            if intent_type == IntentType.CREATE_JOURNAL:
                raise ValidationError("org_entity_id is required.")

            stmt = select(CpEntity).where(
                CpEntity.tenant_id == tenant_id,
            ).order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
            result = await self._db.execute(stmt)
            entity = result.scalars().first()
            if entity is None:
                raise ValidationError("Entity is required for governed intent scope.")
            return entity
        if target_id is None:
            raise ValidationError(f"{intent_type.value} requires a target journal.")
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
        if entity is None:
            raise ValidationError("Target journal does not belong to tenant.")
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
