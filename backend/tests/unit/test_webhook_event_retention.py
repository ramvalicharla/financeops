from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.payment import WebhookEvent
from financeops.tasks.celery_app import cleanup_webhook_events_for_retention


def _webhook_event_row(*, tenant_id: uuid.UUID, event_id: str, created_at: datetime) -> WebhookEvent:
    return WebhookEvent(
        tenant_id=tenant_id,
        chain_hash=f"{event_id:0<64}"[:64],
        previous_hash="0" * 64,
        provider="stripe",
        provider_event_id=event_id,
        event_type="invoice.paid",
        payload={"id": event_id},
        processed=False,
        processed_at=None,
        processing_error=None,
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_cleanup_webhook_events_for_retention_removes_only_rows_older_than_cutoff(
    api_session_factory,
) -> None:
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with api_session_factory() as db:
        await db.execute(text(append_only_function_sql()))
        await db.execute(text(drop_trigger_sql("webhook_events")))
        await db.execute(text(create_trigger_sql("webhook_events")))

        old_row = _webhook_event_row(
            tenant_id=tenant_id,
            event_id="evt_old_retained",
            created_at=now - timedelta(days=120),
        )
        fresh_row = _webhook_event_row(
            tenant_id=tenant_id,
            event_id="evt_fresh_retained",
            created_at=now - timedelta(days=5),
        )
        db.add_all([old_row, fresh_row])
        await db.commit()

    result = await cleanup_webhook_events_for_retention(retention_days=30)

    assert result["removed_webhook_events"] == 1
    assert result["stale_webhook_events"] == 1
    assert result["retention_days"] == 30
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0

    async with api_session_factory() as db:
        remaining_rows = list(
            (
                await db.execute(
                    select(WebhookEvent)
                    .where(WebhookEvent.tenant_id == tenant_id)
                    .order_by(WebhookEvent.created_at.asc(), WebhookEvent.id.asc())
                )
            ).scalars()
        )

    assert [row.provider_event_id for row in remaining_rows] == ["evt_fresh_retained"]


@pytest.mark.asyncio
async def test_cleanup_webhook_events_for_retention_reports_zero_row_scan(
    api_session_factory,
) -> None:
    result = await cleanup_webhook_events_for_retention(retention_days=30)

    assert result["removed_webhook_events"] == 0
    assert result["stale_webhook_events"] == 0
    assert result["retention_days"] == 30
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0
