from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.consolidation import ConsolidationRunEvent
from financeops.services.consolidation.lineage_validation import validate_lineage_completeness
from financeops.services.consolidation.run_events import append_run_event
from financeops.services.consolidation.service_types import TERMINAL_EVENT_TYPES


async def finalize_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
    event_type: str,
    metadata_json: dict[str, Any] | None,
) -> ConsolidationRunEvent:
    if event_type not in TERMINAL_EVENT_TYPES:
        raise ValidationError("Invalid terminal run event type")
    if event_type in {"completed", "completed_with_unexplained"}:
        lineage = await validate_lineage_completeness(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
        )
        if not lineage.is_complete:
            await append_run_event(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
                user_id=user_id,
                event_type="failed",
                idempotency_key="terminal:failed:lineage_incomplete",
                metadata_json=lineage.as_metadata(),
                correlation_id=correlation_id,
            )
            raise ValidationError("LINEAGE_INCOMPLETE")
    existing_terminal = await session.execute(
        select(ConsolidationRunEvent)
        .where(
            ConsolidationRunEvent.tenant_id == tenant_id,
            ConsolidationRunEvent.run_id == run_id,
            ConsolidationRunEvent.event_type.in_(list(TERMINAL_EVENT_TYPES)),
        )
        .order_by(desc(ConsolidationRunEvent.event_seq))
        .limit(1)
    )
    terminal = existing_terminal.scalar_one_or_none()
    if terminal is not None:
        return terminal
    return await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=event_type,
        idempotency_key=f"terminal:{event_type}",
        metadata_json=metadata_json,
        correlation_id=correlation_id,
    )
