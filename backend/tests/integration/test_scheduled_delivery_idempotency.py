from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.scheduled_delivery import DeliveryLog, DeliverySchedule
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.modules.scheduled_delivery.application.delivery_service import DeliveryService
from financeops.modules.scheduled_delivery.infrastructure.repository import DeliveryRepository
from financeops.modules.scheduled_delivery.tasks import _deliver_schedule_once


def _schedule_payload(
    *,
    source_definition_id: uuid.UUID,
    cron_expression: str,
    name: str,
) -> dict[str, object]:
    return {
        "name": name,
        "description": "scheduled delivery idempotency test",
        "schedule_type": "REPORT",
        "source_definition_id": str(source_definition_id),
        "cron_expression": cron_expression,
        "timezone": "UTC",
        "recipients": [{"type": "EMAIL", "address": "ops@example.com"}],
        "export_format": "PDF",
        "config": {},
    }


async def _insert_schedule(
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    recipient_type: str,
    recipient_address: str,
) -> DeliverySchedule:
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        try:
            row = DeliverySchedule(
                tenant_id=tenant_id,
                name=f"Schedule-{uuid.uuid4().hex[:8]}",
                description="delivery task idempotency",
                schedule_type="REPORT",
                source_definition_id=uuid.uuid4(),
                cron_expression="0 9 * * 1",
                timezone="UTC",
                recipients=[{"type": recipient_type, "address": recipient_address}],
                export_format="PDF",
                is_active=True,
                next_run_at=datetime.now(UTC),
                created_by=created_by,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            return row
        finally:
            await clear_tenant_context(session)


async def _count_delivered_logs(
    *,
    tenant_id: uuid.UUID,
    schedule_id: uuid.UUID,
    idempotency_key: str,
    channel_type: str,
) -> int:
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        try:
            return (
                await session.execute(
                    select(func.count())
                    .select_from(DeliveryLog)
                    .where(
                        DeliveryLog.schedule_id == schedule_id,
                        DeliveryLog.idempotency_key == idempotency_key,
                        DeliveryLog.channel_type == channel_type,
                        DeliveryLog.status == "DELIVERED",
                    )
                )
            ).scalar_one()
        finally:
            await clear_tenant_context(session)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_celery_retry_does_not_duplicate_email_delivery(
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = await _insert_schedule(
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        recipient_type="email",
        recipient_address="ops@example.com",
    )
    calls: list[str | None] = []

    async def _fake_trigger_schedule(
        self,
        *,
        db: AsyncSession,
        schedule_id: uuid.UUID,
        tenant_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> list[DeliveryLog]:
        calls.append(idempotency_key)
        log = await DeliveryRepository().create_log(
            db=db,
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            channel_type="EMAIL",
            recipient_address="ops@example.com",
            source_run_id=uuid.uuid4(),
            status="DELIVERED",
            completed_at=datetime.now(UTC),
            idempotency_key=idempotency_key,
            response_metadata={"delivery": "ok"},
        )
        return [log]

    monkeypatch.setattr(DeliveryService, "trigger_schedule", _fake_trigger_schedule)

    first = await _deliver_schedule_once(schedule.id, test_user.tenant_id, "delivery-email-idem")
    second = await _deliver_schedule_once(schedule.id, test_user.tenant_id, "delivery-email-idem")

    assert first["status"] == "DELIVERED"
    assert first["duplicate"] is False
    assert second["status"] == "DELIVERED"
    assert second["duplicate"] is True
    assert calls == ["delivery-email-idem"]
    assert (
        await _count_delivered_logs(
            tenant_id=test_user.tenant_id,
            schedule_id=schedule.id,
            idempotency_key="delivery-email-idem",
            channel_type="EMAIL",
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_celery_retry_does_not_duplicate_webhook_delivery(
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = await _insert_schedule(
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        recipient_type="webhook",
        recipient_address="https://example.com/hook",
    )
    calls: list[str | None] = []

    async def _fake_trigger_schedule(
        self,
        *,
        db: AsyncSession,
        schedule_id: uuid.UUID,
        tenant_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> list[DeliveryLog]:
        calls.append(idempotency_key)
        log = await DeliveryRepository().create_log(
            db=db,
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            channel_type="WEBHOOK",
            recipient_address="https://example.com/hook",
            source_run_id=uuid.uuid4(),
            status="DELIVERED",
            completed_at=datetime.now(UTC),
            idempotency_key=idempotency_key,
            response_metadata={"delivery": "ok"},
        )
        return [log]

    monkeypatch.setattr(DeliveryService, "trigger_schedule", _fake_trigger_schedule)

    first = await _deliver_schedule_once(schedule.id, test_user.tenant_id, "delivery-webhook-idem")
    second = await _deliver_schedule_once(schedule.id, test_user.tenant_id, "delivery-webhook-idem")

    assert first["status"] == "DELIVERED"
    assert first["duplicate"] is False
    assert second["status"] == "DELIVERED"
    assert second["duplicate"] is True
    assert calls == ["delivery-webhook-idem"]
    assert (
        await _count_delivered_logs(
            tenant_id=test_user.tenant_id,
            schedule_id=schedule.id,
            idempotency_key="delivery-webhook-idem",
            channel_type="WEBHOOK",
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_cron_expression_rejected_with_422(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=_schedule_payload(
            source_definition_id=uuid.uuid4(),
            cron_expression="61 24 * * *",
            name="Invalid Cron",
        ),
    )

    body = response.json()
    assert response.status_code == 422
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CRON_EXPRESSION"
    assert body["error"]["message"] == "Invalid cron expression"
    assert body["error"]["details"] == {
        "value": "61 24 * * *",
        "hint": "Example: '0 9 * * 1' (every Monday at 9am)",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_valid_cron_expressions_accepted(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    expressions = [
        "0 9 * * 1",
        "*/15 * * * *",
        "0 0 1 * *",
    ]

    for expression in expressions:
        response = await async_client.post(
            "/api/v1/delivery/schedules",
            headers={"Authorization": f"Bearer {test_access_token}"},
            json=_schedule_payload(
                source_definition_id=uuid.uuid4(),
                cron_expression=expression,
                name=f"Valid Cron {uuid.uuid4().hex[:8]}",
            ),
        )

        assert response.status_code == 201
        assert response.json()["data"]["cron_expression"] == expression
