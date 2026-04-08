from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.service import IntentActor, IntentService


def _normalize_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload


def build_governed_idempotency_key(
    *,
    intent_type: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_role: str | None,
    target_id: uuid.UUID | None,
    namespace: str,
    payload: Any | None = None,
) -> str:
    fingerprint = {
        "namespace": namespace,
        "intent_type": intent_type,
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "actor_role": actor_role or "",
        "target_id": str(target_id) if target_id is not None else "",
        "payload": _normalize_payload(payload),
    }
    raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GovernedJournalMutationResult:
    intent_id: uuid.UUID
    status: str
    job_id: uuid.UUID | None
    next_action: str
    record_refs: dict[str, Any] | None
    journal_id: uuid.UUID | None

    def model_dump(self) -> dict[str, Any]:
        return {
            "intent_id": str(self.intent_id),
            "status": self.status,
            "job_id": str(self.job_id) if self.job_id is not None else None,
            "next_action": self.next_action,
            "record_refs": self.record_refs,
            "journal_id": str(self.journal_id) if self.journal_id is not None else None,
        }

    def require_journal_id(self) -> uuid.UUID:
        if self.journal_id is None:
            raise ValidationError("Governed journal mutation did not return a journal_id.")
        return self.journal_id


async def submit_governed_journal_intent(
    db: AsyncSession,
    *,
    intent_type: Any,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_role: str,
    source_channel: str,
    namespace: str,
    payload: Any | None = None,
    target_id: uuid.UUID | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> GovernedJournalMutationResult:
    normalized_payload = _normalize_payload(payload)
    result = await IntentService(db).submit_intent(
        intent_type=intent_type,
        actor=IntentActor(
            user_id=user_id,
            tenant_id=tenant_id,
            role=actor_role,
            source_channel=source_channel,
            request_id=request_id,
            correlation_id=correlation_id,
        ),
        payload=normalized_payload,
        target_id=target_id,
        idempotency_key=build_governed_idempotency_key(
            intent_type=getattr(intent_type, "value", str(intent_type)),
            tenant_id=tenant_id,
            user_id=user_id,
            actor_role=actor_role,
            target_id=target_id,
            namespace=namespace,
            payload=normalized_payload,
        ),
    )
    journal_id: uuid.UUID | None = None
    if result.record_refs and result.record_refs.get("journal_id") is not None:
        journal_id = uuid.UUID(str(result.record_refs["journal_id"]))
    elif target_id is not None:
        journal_id = target_id
    return GovernedJournalMutationResult(
        intent_id=result.intent_id,
        status=result.status,
        job_id=result.job_id,
        next_action=result.next_action,
        record_refs=result.record_refs,
        journal_id=journal_id,
    )
