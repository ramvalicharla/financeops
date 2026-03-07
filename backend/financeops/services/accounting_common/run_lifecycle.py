from __future__ import annotations

from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Mapping
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.services.accounting_common.run_base_models import (
    RunCreateResult,
    RunStatusSnapshot,
    TRunEventModel,
    TRunModel,
)
from financeops.services.accounting_common.run_events_base import (
    RUN_EVENT_ACCEPTED,
    RUN_EVENT_FAILED,
)
from financeops.services.accounting_common.run_signature import build_request_signature
from financeops.services.accounting_common.run_validation import (
    LineageValidationResult,
    ensure_lineage_complete,
    ensure_model_columns,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter

_REQUIRED_RUN_COLUMNS = ("id", "tenant_id", "request_signature")
_REQUIRED_EVENT_COLUMNS = (
    "id",
    "tenant_id",
    "run_id",
    "event_seq",
    "event_type",
    "event_time",
    "idempotency_key",
)


async def ensure_idempotent_event(
    session: AsyncSession,
    *,
    event_model: type[TRunEventModel],
    run_id: UUID,
    event_type: str,
    idempotency_key: str,
) -> TRunEventModel | None:
    ensure_model_columns(event_model, _REQUIRED_EVENT_COLUMNS)
    result = await session.execute(
        select(event_model).where(
            getattr(event_model, "run_id") == run_id,
            getattr(event_model, "event_type") == event_type,
            getattr(event_model, "idempotency_key") == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def append_event(
    session: AsyncSession,
    *,
    event_model: type[TRunEventModel],
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    event_type: str,
    idempotency_key: str,
    metadata_json: Mapping[str, Any] | None,
    correlation_id: str | None,
    audit_namespace: str,
) -> TRunEventModel:
    existing = await ensure_idempotent_event(
        session,
        event_model=event_model,
        run_id=run_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        return existing

    event_seq_result = await session.execute(
        select(func.max(getattr(event_model, "event_seq"))).where(
            getattr(event_model, "run_id") == run_id
        )
    )
    event_seq = int(event_seq_result.scalar_one() or 0) + 1

    values: dict[str, Any] = {
        "run_id": run_id,
        "event_seq": event_seq,
        "event_type": event_type,
        "event_time": datetime.now(UTC),
        "idempotency_key": idempotency_key,
    }
    if hasattr(event_model, "metadata_json"):
        values["metadata_json"] = dict(metadata_json or {}) if metadata_json is not None else None
    if hasattr(event_model, "correlation_id"):
        values["correlation_id"] = correlation_id

    try:
        return await AuditWriter.insert_financial_record(
            session,
            model_class=event_model,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "event_seq": event_seq,
                "event_type": event_type,
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
            },
            values=values,
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action=f"{audit_namespace}.run.event.created",
                resource_type=event_model.__tablename__,
                new_value={
                    "run_id": str(run_id),
                    "event_type": event_type,
                    "event_seq": event_seq,
                    "correlation_id": correlation_id,
                },
            ),
        )
    except IntegrityError:
        existing_retry = await ensure_idempotent_event(
            session,
            event_model=event_model,
            run_id=run_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
        )
        if existing_retry is None:
            raise
        return existing_retry


async def derive_latest_status(
    session: AsyncSession,
    *,
    run_model: type[TRunModel],
    event_model: type[TRunEventModel],
    tenant_id: UUID,
    run_id: UUID,
) -> RunStatusSnapshot:
    ensure_model_columns(run_model, _REQUIRED_RUN_COLUMNS)
    ensure_model_columns(event_model, _REQUIRED_EVENT_COLUMNS)

    run_result = await session.execute(
        select(run_model).where(
            getattr(run_model, "tenant_id") == tenant_id,
            getattr(run_model, "id") == run_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Run not found")

    event_result = await session.execute(
        select(event_model)
        .where(
            getattr(event_model, "tenant_id") == tenant_id,
            getattr(event_model, "run_id") == run_id,
        )
        .order_by(desc(getattr(event_model, "event_seq")))
        .limit(1)
    )
    latest = event_result.scalar_one_or_none()
    if latest is None:
        raise NotFoundError("Run has no lifecycle events")

    metadata: dict[str, Any] | None = None
    if hasattr(latest, "metadata_json"):
        raw_metadata = getattr(latest, "metadata_json")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else raw_metadata

    return RunStatusSnapshot(
        run_id=run_id,
        status=str(getattr(latest, "event_type")),
        event_seq=int(getattr(latest, "event_seq")),
        event_time=getattr(latest, "event_time"),
        metadata=metadata,
    )


async def create_run_header(
    session: AsyncSession,
    *,
    run_model: type[TRunModel],
    event_model: type[TRunEventModel],
    tenant_id: UUID,
    initiated_by: UUID | None,
    request_payload: Mapping[str, Any],
    workflow_id: str,
    correlation_id: str | None,
    audit_namespace: str,
    run_values: Mapping[str, Any] | None = None,
    accepted_event_type: str = RUN_EVENT_ACCEPTED,
) -> RunCreateResult:
    ensure_model_columns(run_model, _REQUIRED_RUN_COLUMNS)
    ensure_model_columns(event_model, _REQUIRED_EVENT_COLUMNS)

    request_signature = build_request_signature(dict(request_payload))
    existing_result = await session.execute(
        select(run_model).where(
            getattr(run_model, "tenant_id") == tenant_id,
            getattr(run_model, "request_signature") == request_signature,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        latest_status = await derive_latest_status(
            session,
            run_model=run_model,
            event_model=event_model,
            tenant_id=tenant_id,
            run_id=getattr(existing, "id"),
        )
        return RunCreateResult(
            run_id=getattr(existing, "id"),
            workflow_id=str(getattr(existing, "workflow_id")),
            request_signature=request_signature,
            status=latest_status.status,
            created_new=False,
        )

    values: dict[str, Any] = {
        "request_signature": request_signature,
        "workflow_id": workflow_id,
    }
    if hasattr(run_model, "correlation_id"):
        values["correlation_id"] = correlation_id
    if hasattr(run_model, "configuration_json"):
        values["configuration_json"] = dict(request_payload)
    if hasattr(run_model, "initiated_by") and initiated_by is not None:
        values["initiated_by"] = initiated_by
    if run_values:
        values.update(dict(run_values))

    run = await AuditWriter.insert_financial_record(
        session,
        model_class=run_model,
        tenant_id=tenant_id,
        record_data={
            "request_signature": request_signature,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
        },
        values=values,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action=f"{audit_namespace}.run.created",
            resource_type=run_model.__tablename__,
            new_value={
                "request_signature": request_signature,
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
            },
        ),
    )

    await append_event(
        session,
        event_model=event_model,
        tenant_id=tenant_id,
        run_id=getattr(run, "id"),
        user_id=initiated_by,
        event_type=accepted_event_type,
        idempotency_key="run-created",
        metadata_json={"workflow_id": workflow_id},
        correlation_id=correlation_id,
        audit_namespace=audit_namespace,
    )

    return RunCreateResult(
        run_id=getattr(run, "id"),
        workflow_id=workflow_id,
        request_signature=request_signature,
        status=accepted_event_type,
        created_new=True,
    )


async def validate_lineage_before_finalize(
    session: AsyncSession,
    *,
    event_model: type[TRunEventModel],
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
    audit_namespace: str,
    lineage_validator: Callable[[], LineageValidationResult | Awaitable[LineageValidationResult]],
) -> LineageValidationResult:
    outcome = lineage_validator()
    result = await outcome if isawaitable(outcome) else outcome
    if not isinstance(result, LineageValidationResult):
        raise ValidationError("Lineage validator must return LineageValidationResult")

    try:
        ensure_lineage_complete(result)
    except ValidationError:
        await append_event(
            session,
            event_model=event_model,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            event_type=RUN_EVENT_FAILED,
            idempotency_key="terminal:failed:lineage_incomplete",
            metadata_json=result.as_metadata(),
            correlation_id=correlation_id,
            audit_namespace=audit_namespace,
        )
        raise

    return result
