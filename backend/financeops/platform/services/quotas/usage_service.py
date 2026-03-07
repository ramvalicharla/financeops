from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.tenant_quota_assignments import CpTenantQuotaAssignment
from financeops.platform.db.models.tenant_quota_usage_events import CpTenantQuotaUsageEvent
from financeops.platform.db.models.tenant_quota_windows import CpTenantQuotaWindow
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


def _compute_window(now: datetime, *, window_type: str, window_seconds: int) -> tuple[datetime, datetime]:
    if window_type == "tumbling":
        epoch = int(now.timestamp())
        start = epoch - (epoch % window_seconds)
        window_start = datetime.fromtimestamp(start, tz=UTC)
        return window_start, window_start + timedelta(seconds=window_seconds)
    if window_type == "sliding":
        return now - timedelta(seconds=window_seconds), now
    raise ValidationError("Unsupported quota window_type")


async def _get_active_assignment(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quota_type: str,
    as_of: datetime,
) -> CpTenantQuotaAssignment:
    result = await session.execute(
        select(CpTenantQuotaAssignment)
        .where(
            CpTenantQuotaAssignment.tenant_id == tenant_id,
            CpTenantQuotaAssignment.quota_type == quota_type,
            CpTenantQuotaAssignment.effective_from <= as_of,
            (CpTenantQuotaAssignment.effective_to.is_(None) | (CpTenantQuotaAssignment.effective_to > as_of)),
        )
        .order_by(CpTenantQuotaAssignment.effective_from.desc())
    )
    assignment = result.scalars().first()
    if assignment is None:
        raise ValidationError(f"No active quota assignment for {quota_type}")
    return assignment


async def check_and_record_usage(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quota_type: str,
    usage_delta: int,
    operation_id: uuid.UUID,
    idempotency_key: str,
    request_fingerprint: str,
    source_layer: str,
    actor_user_id: uuid.UUID | None,
    correlation_id: str,
) -> dict:
    now = _now()
    assignment = await _get_active_assignment(
        session,
        tenant_id=tenant_id,
        quota_type=quota_type,
        as_of=now,
    )

    existing_result = await session.execute(
        select(CpTenantQuotaUsageEvent).where(
            CpTenantQuotaUsageEvent.tenant_id == tenant_id,
            CpTenantQuotaUsageEvent.quota_type == quota_type,
            CpTenantQuotaUsageEvent.operation_id == operation_id,
            CpTenantQuotaUsageEvent.idempotency_key == idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return {
            "allowed": True,
            "code": "IDEMPOTENT_REPLAY",
            "enforcement_mode": assignment.enforcement_mode,
            "window_end": existing.window_end,
            "consumed_value": usage_delta,
            "max_value": assignment.max_value,
            "usage_event_id": str(existing.id),
        }

    window_start, window_end = _compute_window(
        now,
        window_type=assignment.window_type,
        window_seconds=assignment.window_seconds,
    )

    consumed_result = await session.execute(
        select(func.coalesce(func.sum(CpTenantQuotaUsageEvent.usage_delta), 0)).where(
            CpTenantQuotaUsageEvent.tenant_id == tenant_id,
            CpTenantQuotaUsageEvent.quota_type == quota_type,
            CpTenantQuotaUsageEvent.window_start == window_start,
            CpTenantQuotaUsageEvent.window_end == window_end,
        )
    )
    consumed = int(consumed_result.scalar_one() or 0)
    projected = consumed + usage_delta

    if projected > assignment.max_value:
        return {
            "allowed": False,
            "code": "QUOTA_EXCEEDED",
            "enforcement_mode": assignment.enforcement_mode,
            "window_end": window_end,
            "consumed_value": consumed,
            "max_value": assignment.max_value,
            "usage_event_id": None,
        }

    event = await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantQuotaUsageEvent,
        tenant_id=tenant_id,
        record_data={
            "quota_type": quota_type,
            "operation_id": str(operation_id),
            "idempotency_key": idempotency_key,
            "usage_delta": usage_delta,
        },
        values={
            "quota_type": quota_type,
            "usage_delta": usage_delta,
            "operation_id": operation_id,
            "idempotency_key": idempotency_key,
            "request_fingerprint": request_fingerprint,
            "source_layer": source_layer,
            "window_start": window_start,
            "window_end": window_end,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.quota.usage.recorded",
            resource_type="cp_tenant_quota_usage_event",
            new_value={"quota_type": quota_type, "usage_delta": usage_delta, "projected": projected},
        ),
    )

    await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantQuotaWindow,
        tenant_id=tenant_id,
        record_data={
            "quota_type": quota_type,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "consumed_value": projected,
        },
        values={
            "quota_type": quota_type,
            "window_start": window_start,
            "window_end": window_end,
            "consumed_value": projected,
            "last_event_id": event.id,
            "updated_at": now,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.quota.window.snapshot",
            resource_type="cp_tenant_quota_window",
            new_value={"quota_type": quota_type, "consumed_value": projected},
        ),
    )

    return {
        "allowed": True,
        "code": "ALLOWED",
        "enforcement_mode": assignment.enforcement_mode,
        "window_end": window_end,
        "consumed_value": projected,
        "max_value": assignment.max_value,
        "usage_event_id": str(event.id),
    }
