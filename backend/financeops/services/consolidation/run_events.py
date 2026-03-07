from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.consolidation import ConsolidationRunEvent
from financeops.services.audit_writer import AuditEvent, AuditWriter

from financeops.services.consolidation.run_store import get_run_or_raise


async def _next_event_seq(session: AsyncSession, *, run_id: UUID) -> int:
    result = await session.execute(
        select(func.max(ConsolidationRunEvent.event_seq)).where(
            ConsolidationRunEvent.run_id == run_id
        )
    )
    max_seq = result.scalar_one()
    return int(max_seq or 0) + 1


async def _find_existing_event(
    session: AsyncSession,
    *,
    run_id: UUID,
    event_type: str,
    idempotency_key: str,
) -> ConsolidationRunEvent | None:
    result = await session.execute(
        select(ConsolidationRunEvent).where(
            ConsolidationRunEvent.run_id == run_id,
            ConsolidationRunEvent.event_type == event_type,
            ConsolidationRunEvent.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def append_run_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    event_type: str,
    idempotency_key: str,
    metadata_json: dict[str, Any] | None,
    correlation_id: str | None,
) -> ConsolidationRunEvent:
    existing = await _find_existing_event(
        session,
        run_id=run_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        return existing

    event_seq = await _next_event_seq(session, run_id=run_id)
    try:
        return await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationRunEvent,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "event_seq": event_seq,
                "event_type": event_type,
                "idempotency_key": idempotency_key,
            },
            values={
                "run_id": run_id,
                "event_seq": event_seq,
                "event_type": event_type,
                "event_time": datetime.now(UTC),
                "idempotency_key": idempotency_key,
                "metadata_json": metadata_json,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.run.event.created",
                resource_type="consolidation_run_event",
                new_value={
                    "run_id": str(run_id),
                    "event_type": event_type,
                    "event_seq": event_seq,
                    "correlation_id": correlation_id,
                },
            ),
        )
    except IntegrityError:
        existing_retry = await _find_existing_event(
            session,
            run_id=run_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
        )
        if existing_retry is None:
            raise
        return existing_retry


async def get_latest_run_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> ConsolidationRunEvent:
    await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    result = await session.execute(
        select(ConsolidationRunEvent)
        .where(
            ConsolidationRunEvent.tenant_id == tenant_id,
            ConsolidationRunEvent.run_id == run_id,
        )
        .order_by(desc(ConsolidationRunEvent.event_seq))
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError("Consolidation run has no lifecycle events")
    return event


async def mark_run_running(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> ConsolidationRunEvent:
    return await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type="running",
        idempotency_key="stage-running",
        metadata_json=None,
        correlation_id=correlation_id,
    )
