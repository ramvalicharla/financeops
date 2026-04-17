from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, InternalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.scheduled_delivery import DeliveryLog, DeliverySchedule  # noqa: F401
from financeops.db.rls import set_tenant_context


async def _insert_schedule(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    schedule_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO delivery_schedules (
                id, tenant_id, name, description, schedule_type, source_definition_id,
                cron_expression, timezone, recipients, export_format, is_active,
                next_run_at, config, created_by, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :name, :description, :schedule_type, :source_definition_id,
                :cron_expression, :timezone, CAST(:recipients AS jsonb), :export_format, :is_active,
                :next_run_at, CAST(:config AS jsonb), :created_by, :created_at, :updated_at
            )
            """
        ),
        {
            "id": str(schedule_id),
            "tenant_id": str(tenant_id),
            "name": "Weekly Board Pack",
            "description": "delivery migration test",
            "schedule_type": "BOARD_PACK",
            "source_definition_id": str(uuid.uuid4()),
            "cron_expression": "0 8 * * 1",
            "timezone": "UTC",
            "recipients": json.dumps([{"type": "email", "address": "ops@example.com"}]),
            "export_format": "PDF",
            "is_active": True,
            "next_run_at": datetime.now(UTC),
            "config": json.dumps({}),
            "created_by": str(tenant_id),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )
    await session.flush()
    return schedule_id


async def _insert_log(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    schedule_id: uuid.UUID,
    *,
    status: str = "PENDING",
) -> uuid.UUID:
    log_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO delivery_logs (
                id, tenant_id, schedule_id, status, channel_type,
                recipient_address, response_metadata, created_at
            ) VALUES (
                :id, :tenant_id, :schedule_id, :status, :channel_type,
                :recipient_address, CAST(:response_metadata AS jsonb), :created_at
            )
            """
        ),
        {
            "id": str(log_id),
            "tenant_id": str(tenant_id),
            "schedule_id": str(schedule_id),
            "status": status,
            "channel_type": "EMAIL",
            "recipient_address": "ops@example.com",
            "response_metadata": json.dumps({}),
            "created_at": datetime.now(UTC),
        },
    )
    await session.flush()
    return log_id


async def _install_append_only_guard(session: AsyncSession, table_name: str) -> None:
    await session.execute(text(append_only_function_sql()))
    await session.execute(text(drop_trigger_sql(table_name)))
    await session.execute(text(create_trigger_sql(table_name)))
    await session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_207_delivery_tables_exist_with_expected_columns(async_session: AsyncSession) -> None:
    expected = {
        "delivery_schedules": {
            "id",
            "tenant_id",
            "name",
            "description",
            "schedule_type",
            "source_definition_id",
            "cron_expression",
            "timezone",
            "recipients",
            "export_format",
            "is_active",
            "last_triggered_at",
            "next_run_at",
            "config",
            "created_by",
            "created_at",
            "updated_at",
        },
        "delivery_logs": {
            "id",
            "tenant_id",
            "schedule_id",
            "triggered_at",
            "completed_at",
            "status",
            "channel_type",
            "recipient_address",
            "source_run_id",
            "error_message",
            "retry_count",
            "idempotency_key",
            "response_metadata",
            "created_at",
        },
    }

    for table_name, required_columns in expected.items():
        rows = await async_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name=:table_name
                """
            ),
            {"table_name": table_name},
        )
        actual_columns = {str(row[0]) for row in rows.all()}
        assert required_columns.issubset(actual_columns)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_208_append_only_trigger_blocks_update_on_delivery_logs(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    schedule_id = await _insert_schedule(async_session, tenant_id)
    log_id = await _insert_log(async_session, tenant_id, schedule_id)
    await _install_append_only_guard(async_session, "delivery_logs")
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
        await async_session.execute(
            text("UPDATE delivery_logs SET status='RUNNING' WHERE id=:id"),
            {"id": log_id},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_209_append_only_trigger_blocks_delete_on_delivery_logs(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    schedule_id = await _insert_schedule(async_session, tenant_id)
    log_id = await _insert_log(async_session, tenant_id, schedule_id)
    await _install_append_only_guard(async_session, "delivery_logs")
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError, DBAPIError)):
        await async_session.execute(
            text("DELETE FROM delivery_logs WHERE id=:id"),
            {"id": log_id},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_210_update_on_delivery_schedules_is_allowed(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    schedule_id = await _insert_schedule(async_session, tenant_id)
    await async_session.execute(
        text("UPDATE delivery_schedules SET name='Updated schedule' WHERE id=:id"),
        {"id": schedule_id},
    )
    await async_session.commit()
    await set_tenant_context(async_session, tenant_id)

    updated_name = (
        await async_session.execute(
            text("SELECT name FROM delivery_schedules WHERE id=:id"),
            {"id": schedule_id},
        )
    ).scalar_one()
    assert updated_name == "Updated schedule"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_211_rls_isolates_delivery_schedules_by_tenant(async_session: AsyncSession) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(text("ALTER TABLE delivery_schedules ENABLE ROW LEVEL SECURITY"))
    await async_session.execute(text("ALTER TABLE delivery_schedules FORCE ROW LEVEL SECURITY"))
    await async_session.execute(text("DROP POLICY IF EXISTS tenant_isolation ON delivery_schedules"))
    await async_session.execute(
        text(
            """
            CREATE POLICY tenant_isolation ON delivery_schedules
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )
    )

    await set_tenant_context(async_session, tenant_a)
    await _insert_schedule(async_session, tenant_a)
    await async_session.commit()

    await set_tenant_context(async_session, tenant_b)
    await _insert_schedule(async_session, tenant_b)
    await async_session.commit()

    await set_tenant_context(async_session, tenant_a)
    count_a = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM delivery_schedules
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                """
            )
        )
    ).scalar_one()
    await set_tenant_context(async_session, tenant_b)
    count_b = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM delivery_schedules
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
                """
            )
        )
    ).scalar_one()
    assert count_a == 1
    assert count_b == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_212_delivery_logs_status_check_rejects_invalid_value(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    schedule_id = await _insert_schedule(async_session, tenant_id)
    with pytest.raises(IntegrityError):
        await _insert_log(
            async_session,
            tenant_id,
            schedule_id,
            status="INVALID_STATUS",
        )
