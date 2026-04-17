from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryExportFormat,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    Recipient,
    ScheduleDefinitionSchema,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _create_schedule_payload(source_definition_id: uuid.UUID) -> dict:
    return {
        "name": "Weekly Finance Report",
        "description": "API schedule test",
        "schedule_type": "REPORT",
        "source_definition_id": str(source_definition_id),
        "cron_expression": "0 8 * * 1",
        "timezone": "UTC",
        "recipients": [{"type": "EMAIL", "address": "ops@example.com"}],
        "export_format": "PDF",
        "config": {},
    }


async def _create_schedule(
    client: AsyncClient,
    token: str,
    source_definition_id: uuid.UUID,
) -> dict:
    response = await client.post(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {token}"},
        json=_create_schedule_payload(source_definition_id),
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_213_create_schedule_returns_201(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=_create_schedule_payload(uuid.uuid4()),
    )
    assert response.status_code == 201
    assert response.json()["data"]["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_214_trigger_schedule_returns_202_and_enqueues_task(
    async_client: AsyncClient,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = await _create_schedule(async_client, test_access_token, uuid.uuid4())
    calls: list[tuple[str, str, str]] = []

    def _fake_delay(schedule_id: str, tenant_id: str, idempotency_key: str) -> None:
        calls.append((schedule_id, tenant_id, idempotency_key))

    monkeypatch.setattr(
        "financeops.modules.scheduled_delivery.api.routes.deliver_schedule_task.delay",
        _fake_delay,
    )

    response = await async_client.post(
        f"/api/v1/delivery/schedules/{schedule['id']}/trigger",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 202
    assert response.json()["data"] == {"schedule_id": schedule["id"], "status": "triggered"}
    assert len(calls) == 1
    assert calls[0][0] == schedule["id"]
    assert calls[0][1] == str(test_user.tenant_id)
    assert calls[0][2].startswith(f"manual-trigger:{schedule['id']}:")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_215_get_logs_returns_logs_for_requested_schedule(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    repository = DeliveryRepository()
    schedule_a = await _create_schedule(async_client, test_access_token, uuid.uuid4())
    schedule_b = await _create_schedule(async_client, test_access_token, uuid.uuid4())
    await set_tenant_context(async_session, test_user.tenant_id)
    await repository.create_log(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schedule_id=uuid.UUID(schedule_a["id"]),
        channel_type="EMAIL",
        recipient_address="ops@example.com",
        source_run_id=uuid.uuid4(),
        status="DELIVERED",
    )
    await repository.create_log(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schedule_id=uuid.UUID(schedule_b["id"]),
        channel_type="EMAIL",
        recipient_address="ops@example.com",
        source_run_id=uuid.uuid4(),
        status="FAILED",
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/delivery/logs?schedule_id={schedule_a['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["schedule_id"] == schedule_a["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_216_delete_schedule_returns_204_and_soft_deletes(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    schedule = await _create_schedule(async_client, test_access_token, uuid.uuid4())

    response = await async_client.delete(
        f"/api/v1/delivery/schedules/{schedule['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 204

    await set_tenant_context(async_session, test_user.tenant_id)
    is_active = (
        await async_session.execute(
            text("SELECT is_active FROM delivery_schedules WHERE id = CAST(:id AS uuid)"),
            {"id": schedule["id"]},
        )
    ).scalar_one()
    assert is_active is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_217_rls_hides_tenant_b_schedules_from_tenant_a(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _create_schedule(async_client, test_access_token, uuid.uuid4())

    tenant_b_id = uuid.uuid4()
    tenant_b_user_id = uuid.uuid4()
    tenant_b = IamTenant(
        id=tenant_b_id,
        tenant_id=tenant_b_id,
        display_name="Tenant B",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Tenant B",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    tenant_b_user = IamUser(
        id=tenant_b_user_id,
        tenant_id=tenant_b_id,
        email=f"tenantb_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Tenant B User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(tenant_b)
    async_session.add(tenant_b_user)
    await async_session.flush()

    await set_tenant_context(async_session, tenant_b_id)
    repository = DeliveryRepository()
    await repository.create_schedule(
        db=async_session,
        tenant_id=tenant_b_id,
        schema=ScheduleDefinitionSchema(
            name="Tenant B schedule",
            description=None,
            schedule_type=ScheduleType.BOARD_PACK,
            source_definition_id=uuid.uuid4(),
            cron_expression="0 9 * * 1",
            timezone="UTC",
            recipients=[Recipient(type=ChannelType.EMAIL, address="tenantb@example.com")],
            export_format=DeliveryExportFormat.PDF,
            config={},
        ),
        created_by=tenant_b_user_id,
    )
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/delivery/schedules",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["data"]]
    assert "Tenant B schedule" not in names
