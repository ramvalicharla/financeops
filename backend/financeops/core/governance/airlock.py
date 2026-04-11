from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.core.governance.guards import ExternalInputGuardContext, GuardEngine
from financeops.db.models.governance_control import AirlockEvent, AirlockItem
from financeops.observability.beta_monitoring import record_airlock_status
from financeops.services.audit_writer import AuditWriter
from financeops.storage.airlock import scan_and_seal


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AirlockActor:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


@dataclass(frozen=True)
class AirlockSubmissionResult:
    item_id: uuid.UUID
    status: str
    quarantine_ref: str | None
    checksum_sha256: str | None
    admitted: bool


class AirlockAdmissionService:
    def __init__(self, *, guard_engine: GuardEngine | None = None) -> None:
        self._guards = guard_engine or GuardEngine()

    async def submit_external_input(
        self,
        db: AsyncSession,
        *,
        source_type: str,
        actor: AirlockActor,
        metadata: dict[str, Any] | None = None,
        content: bytes | None = None,
        file_name: str | None = None,
        entity_id: uuid.UUID | None = None,
        source_reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> AirlockSubmissionResult:
        metadata_json = metadata or {}
        resolved_key = self._normalize_idempotency_key(
            idempotency_key
            or self._idempotency_key(
                source_type=source_type,
                tenant_id=actor.tenant_id,
                source_reference=source_reference,
                metadata=metadata_json,
                content=content,
            )
        )
        existing = (
            await db.execute(
                select(AirlockItem).where(
                    AirlockItem.tenant_id == actor.tenant_id,
                    AirlockItem.source_type == source_type,
                    AirlockItem.idempotency_key == resolved_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return AirlockSubmissionResult(
                item_id=existing.id,
                status=existing.status,
                quarantine_ref=existing.quarantine_ref,
                checksum_sha256=existing.checksum_sha256,
                admitted=existing.status == "ADMITTED",
            )

        item = AirlockItem(
            id=uuid.uuid4(),
            tenant_id=actor.tenant_id,
            entity_id=entity_id,
            source_type=source_type,
            source_reference=source_reference,
            file_name=file_name,
            status="RECEIVED",
            submitted_by_user_id=actor.user_id,
            submitted_at=_utcnow(),
            metadata_json=metadata_json,
            findings_json=[],
            idempotency_key=resolved_key,
        )
        db.add(item)
        await db.flush()
        await self._emit_airlock_transition(
            db,
            item=item,
            event_type="AIRLOCK_RECEIVED",
            actor=actor,
            from_status=None,
            to_status=item.status,
            payload={
                "source_type": source_type,
                "source_reference": source_reference,
                "file_name": file_name,
            },
        )
        record_airlock_status(
            file_id=item.id,
            entity_id=item.entity_id,
            status="uploaded",
            validation_results=[],
            source_type=source_type,
        )

        evaluation = await self._guards.evaluate_external_input(
            db,
            context=ExternalInputGuardContext(
                tenant_id=actor.tenant_id,
                source_type=source_type,
                actor_user_id=actor.user_id,
                actor_role=actor.role,
                entity_id=entity_id,
                file_name=file_name,
                content=content,
                source_reference=source_reference,
                metadata=metadata_json,
                subject_id=str(item.id),
            ),
        )
        item.findings_json = [
            {
                "guard_code": row.guard_code,
                "guard_name": row.guard_name,
                "result": row.result,
                "severity": row.severity,
                "message": row.message,
                "details_json": row.details_json,
                "evaluated_at": row.evaluated_at.isoformat(),
            }
            for row in evaluation.results
        ]
        if not evaluation.overall_passed:
            item.status = "REJECTED"
            item.rejected_at = _utcnow()
            item.rejection_reason = "; ".join(row.message for row in evaluation.blocking_failures)
            await db.flush()
            await self._emit_airlock_transition(
                db,
                item=item,
                event_type="AIRLOCK_REJECTED",
                actor=actor,
                from_status="RECEIVED",
                to_status=item.status,
                payload={"reason": item.rejection_reason},
            )
            record_airlock_status(
                file_id=item.id,
                entity_id=item.entity_id,
                status="rejected",
                validation_results=item.findings_json,
                reason=item.rejection_reason,
                source_type=source_type,
            )
            raise ValidationError(item.rejection_reason or "External input rejected by airlock.")

        if content is not None:
            scan_result = await scan_and_seal(
                content,
                file_name or f"{source_type}.bin",
                str(actor.tenant_id),
            )
            item.mime_type = scan_result.mime_type
            item.size_bytes = scan_result.size_bytes
            item.checksum_sha256 = scan_result.sha256
            item.quarantine_ref = getattr(scan_result, "quarantine_ref", None)
            await db.flush()
            await self._emit_airlock_transition(
                db,
                item=item,
                event_type="AIRLOCK_SCANNED",
                actor=actor,
                from_status="RECEIVED",
                to_status="SCANNING",
                payload={
                    "mime_type": scan_result.mime_type,
                    "size_bytes": scan_result.size_bytes,
                    "checksum_sha256": scan_result.sha256,
                    "quarantine_ref": getattr(scan_result, "quarantine_ref", None),
                    "scan_result": getattr(scan_result, "scan_result", None),
                },
            )
            record_airlock_status(
                file_id=item.id,
                entity_id=item.entity_id,
                status="scanned",
                validation_results=item.findings_json,
                source_type=source_type,
            )

        item.status = "QUARANTINED"
        await db.flush()
        await self._emit_airlock_transition(
            db,
            item=item,
            event_type="AIRLOCK_QUARANTINED",
            actor=actor,
            from_status="RECEIVED",
            to_status=item.status,
            payload={"quarantine_ref": item.quarantine_ref},
        )
        return AirlockSubmissionResult(
            item_id=item.id,
            status=item.status,
            quarantine_ref=item.quarantine_ref,
            checksum_sha256=item.checksum_sha256,
            admitted=False,
        )

    async def admit_airlock_item(
        self,
        db: AsyncSession,
        *,
        item_id: uuid.UUID,
        actor: AirlockActor,
    ) -> AirlockSubmissionResult:
        item = await self.get_item(db, tenant_id=actor.tenant_id, item_id=item_id)
        if item.status == "ADMITTED":
            return AirlockSubmissionResult(
                item_id=item.id,
                status=item.status,
                quarantine_ref=item.quarantine_ref,
                checksum_sha256=item.checksum_sha256,
                admitted=True,
            )
        if item.status != "QUARANTINED":
            raise ValidationError("Only QUARANTINED airlock items can be admitted.")
        item.status = "ADMITTED"
        item.reviewed_by_user_id = actor.user_id
        item.reviewed_at = _utcnow()
        item.admitted_by_user_id = actor.user_id
        item.admitted_at = _utcnow()
        await db.flush()
        await self._emit_airlock_transition(
            db,
            item=item,
            event_type="AIRLOCK_ADMITTED",
            actor=actor,
            from_status="QUARANTINED",
            to_status=item.status,
            payload={"admitted_at": item.admitted_at.isoformat() if item.admitted_at else None},
        )
        record_airlock_status(
            file_id=item.id,
            entity_id=item.entity_id,
            status="admitted",
            validation_results=item.findings_json if isinstance(item.findings_json, list) else [],
            source_type=item.source_type,
        )
        return AirlockSubmissionResult(
            item_id=item.id,
            status=item.status,
            quarantine_ref=item.quarantine_ref,
            checksum_sha256=item.checksum_sha256,
            admitted=True,
        )

    async def reject_airlock_item(
        self,
        db: AsyncSession,
        *,
        item_id: uuid.UUID,
        actor: AirlockActor,
        reason: str,
    ) -> AirlockSubmissionResult:
        item = await self.get_item(db, tenant_id=actor.tenant_id, item_id=item_id)
        if item.status == "ADMITTED":
            raise ValidationError("Admitted airlock items cannot be rejected.")
        item.status = "REJECTED"
        item.reviewed_by_user_id = actor.user_id
        item.reviewed_at = _utcnow()
        item.rejected_at = _utcnow()
        item.rejection_reason = reason
        await db.flush()
        await self._emit_airlock_transition(
            db,
            item=item,
            event_type="AIRLOCK_REJECTED",
            actor=actor,
            from_status="QUARANTINED",
            to_status=item.status,
            payload={"reason": reason},
        )
        record_airlock_status(
            file_id=item.id,
            entity_id=item.entity_id,
            status="rejected",
            validation_results=item.findings_json if isinstance(item.findings_json, list) else [],
            reason=reason,
            source_type=item.source_type,
        )
        return AirlockSubmissionResult(
            item_id=item.id,
            status=item.status,
            quarantine_ref=item.quarantine_ref,
            checksum_sha256=item.checksum_sha256,
            admitted=False,
        )

    async def assert_admitted(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID | None,
        source_type: str | None = None,
    ) -> AirlockItem:
        if item_id is None:
            raise ValidationError("admitted_airlock_item_id is required.")
        item = await self.get_item(db, tenant_id=tenant_id, item_id=item_id)
        if item.status != "ADMITTED":
            raise ValidationError("Airlock item is not admitted.")
        if source_type and item.source_type != source_type:
            raise ValidationError("Airlock item source type does not match downstream mutation.")
        return item

    async def get_item(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> AirlockItem:
        item = (
            await db.execute(
                select(AirlockItem).where(
                    AirlockItem.id == item_id,
                    AirlockItem.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if item is None:
            raise ValidationError("Airlock item was not found.")
        return item

    async def _emit_airlock_transition(
        self,
        db: AsyncSession,
        *,
        item: AirlockItem,
        event_type: str,
        actor: AirlockActor,
        from_status: str | None,
        to_status: str | None,
        payload: dict[str, Any],
    ) -> None:
        await AuditWriter.insert_financial_record(
            db,
            model_class=AirlockEvent,
            tenant_id=item.tenant_id,
            record_data={
                "airlock_item_id": str(item.id),
                "event_type": event_type,
                "to_status": to_status or "",
            },
            values={
                "airlock_item_id": item.id,
                "event_type": event_type,
                "from_status": from_status,
                "to_status": to_status,
                "actor_user_id": actor.user_id,
                "actor_role": actor.role,
                "event_payload_json": payload,
            },
        )
        await emit_governance_event(
            db,
            tenant_id=item.tenant_id,
            module_key="airlock",
            subject_type="airlock_item",
            subject_id=str(item.id),
            event_type=event_type,
            actor=GovernanceActor(user_id=actor.user_id, role=actor.role),
            entity_id=item.entity_id,
            payload=payload,
        )

    @staticmethod
    def _idempotency_key(
        *,
        source_type: str,
        tenant_id: uuid.UUID,
        source_reference: str | None,
        metadata: dict[str, Any],
        content: bytes | None,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(str(tenant_id).encode("utf-8"))
        digest.update(source_type.encode("utf-8"))
        digest.update((source_reference or "").encode("utf-8"))
        digest.update(repr(sorted(metadata.items())).encode("utf-8"))
        if content is not None:
            digest.update(content)
        return digest.hexdigest()

    @staticmethod
    def _normalize_idempotency_key(idempotency_key: str) -> str:
        if len(idempotency_key) <= 128:
            return idempotency_key
        return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
