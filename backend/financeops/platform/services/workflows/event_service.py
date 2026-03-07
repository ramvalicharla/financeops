from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.platform.db.models.workflow_events import CpWorkflowInstanceEvent
from financeops.platform.db.models.workflow_stage_events import CpWorkflowStageEvent
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def append_workflow_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
    event_type: str,
    idempotency_key: str,
    metadata_json: dict[str, Any] | None,
    actor_user_id: uuid.UUID | None,
    correlation_id: str,
) -> CpWorkflowInstanceEvent:
    existing_result = await session.execute(
        select(CpWorkflowInstanceEvent).where(
            CpWorkflowInstanceEvent.tenant_id == tenant_id,
            CpWorkflowInstanceEvent.workflow_instance_id == workflow_instance_id,
            CpWorkflowInstanceEvent.event_type == event_type,
            CpWorkflowInstanceEvent.idempotency_key == idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    seq_result = await session.execute(
        select(func.max(CpWorkflowInstanceEvent.event_seq)).where(
            CpWorkflowInstanceEvent.tenant_id == tenant_id,
            CpWorkflowInstanceEvent.workflow_instance_id == workflow_instance_id,
        )
    )
    event_seq = int(seq_result.scalar_one() or 0) + 1

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpWorkflowInstanceEvent,
        tenant_id=tenant_id,
        record_data={
            "workflow_instance_id": str(workflow_instance_id),
            "event_type": event_type,
            "event_seq": event_seq,
            "idempotency_key": idempotency_key,
        },
        values={
            "workflow_instance_id": workflow_instance_id,
            "event_seq": event_seq,
            "event_type": event_type,
            "event_time": _now(),
            "idempotency_key": idempotency_key,
            "metadata_json": metadata_json,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.workflow.instance_event.appended",
            resource_type="cp_workflow_instance_event",
            new_value={"workflow_instance_id": str(workflow_instance_id), "event_type": event_type, "event_seq": event_seq},
        ),
    )


async def append_stage_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stage_instance_id: uuid.UUID,
    event_type: str,
    idempotency_key: str,
    metadata_json: dict[str, Any] | None,
    actor_user_id: uuid.UUID | None,
    correlation_id: str,
) -> CpWorkflowStageEvent:
    existing_result = await session.execute(
        select(CpWorkflowStageEvent).where(
            CpWorkflowStageEvent.tenant_id == tenant_id,
            CpWorkflowStageEvent.stage_instance_id == stage_instance_id,
            CpWorkflowStageEvent.event_type == event_type,
            CpWorkflowStageEvent.idempotency_key == idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    seq_result = await session.execute(
        select(func.max(CpWorkflowStageEvent.event_seq)).where(
            CpWorkflowStageEvent.tenant_id == tenant_id,
            CpWorkflowStageEvent.stage_instance_id == stage_instance_id,
        )
    )
    event_seq = int(seq_result.scalar_one() or 0) + 1

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpWorkflowStageEvent,
        tenant_id=tenant_id,
        record_data={
            "stage_instance_id": str(stage_instance_id),
            "event_type": event_type,
            "event_seq": event_seq,
            "idempotency_key": idempotency_key,
        },
        values={
            "stage_instance_id": stage_instance_id,
            "event_seq": event_seq,
            "event_type": event_type,
            "event_time": _now(),
            "idempotency_key": idempotency_key,
            "metadata_json": metadata_json,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.workflow.stage_event.appended",
            resource_type="cp_workflow_stage_event",
            new_value={"stage_instance_id": str(stage_instance_id), "event_type": event_type, "event_seq": event_seq},
        ),
    )


async def derive_workflow_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
) -> dict[str, Any]:
    result = await session.execute(
        select(CpWorkflowInstanceEvent)
        .where(
            CpWorkflowInstanceEvent.tenant_id == tenant_id,
            CpWorkflowInstanceEvent.workflow_instance_id == workflow_instance_id,
        )
        .order_by(desc(CpWorkflowInstanceEvent.event_seq))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        raise NotFoundError("Workflow has no events")
    return {
        "workflow_instance_id": str(workflow_instance_id),
        "status": latest.event_type,
        "event_seq": latest.event_seq,
        "event_time": latest.event_time,
        "metadata": latest.metadata_json,
    }


async def derive_stage_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stage_instance_id: uuid.UUID,
) -> dict[str, Any]:
    result = await session.execute(
        select(CpWorkflowStageEvent)
        .where(
            CpWorkflowStageEvent.tenant_id == tenant_id,
            CpWorkflowStageEvent.stage_instance_id == stage_instance_id,
        )
        .order_by(desc(CpWorkflowStageEvent.event_seq))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        raise NotFoundError("Stage has no events")
    return {
        "stage_instance_id": str(stage_instance_id),
        "status": latest.event_type,
        "event_seq": latest.event_seq,
        "event_time": latest.event_time,
        "metadata": latest.metadata_json,
    }
