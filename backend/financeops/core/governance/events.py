from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.governance_control import CanonicalGovernanceEvent
from financeops.services.audit_writer import AuditWriter


@dataclass(frozen=True)
class GovernanceActor:
    user_id: uuid.UUID | None
    role: str | None


async def emit_governance_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_key: str,
    subject_type: str,
    subject_id: str,
    event_type: str,
    actor: GovernanceActor,
    entity_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> CanonicalGovernanceEvent:
    event_payload = payload or {}
    return await AuditWriter.insert_financial_record(
        db,
        model_class=CanonicalGovernanceEvent,
        tenant_id=tenant_id,
        record_data={
            "module_key": module_key,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "event_type": event_type,
        },
        values={
            "entity_id": entity_id,
            "module_key": module_key,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "event_type": event_type,
            "actor_user_id": actor.user_id,
            "actor_role": actor.role,
            "payload_json": event_payload,
        },
    )
