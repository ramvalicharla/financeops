from __future__ import annotations

import smtplib
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import decrypt_field
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.erp_sync import ExternalConnection, ExternalConnectionVersion
from financeops.db.models.scheduled_delivery import DeliverySchedule
from financeops.db.rls import set_tenant_context
from financeops.modules.secret_rotation.models import SecretRotationLog
from financeops.modules.secret_rotation.service import (
    PLATFORM_TENANT_ID,
    get_rotation_log,
    rotate_erp_api_key,
    rotate_smtp_credentials,
    rotate_webhook_secret,
)
from financeops.services.audit_writer import AuditWriter


def _read_webhook_secret(config: dict | None) -> str:
    payload = dict(config or {})
    encrypted = str(payload.get("webhook_secret_enc") or "").strip()
    if encrypted:
        return decrypt_field(encrypted)
    return str(payload.get("webhook_secret") or "")


def _read_api_key(snapshot: dict | None) -> str:
    payload = dict(snapshot or {})
    value = str(payload.get("api_key") or payload.get("secret_ref") or "")
    if not value:
        return ""
    try:
        return decrypt_field(value)
    except Exception:
        return value


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def ensure_secret_rotation_schema(engine) -> None:
    """Ensure secret_rotation_log table, append-only trigger, and RLS policy exist for tests."""
    async with engine.begin() as conn:
        await conn.run_sync(SecretRotationLog.__table__.create, checkfirst=True)
        await conn.execute(text("ALTER TABLE secret_rotation_log ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE secret_rotation_log FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("DROP POLICY IF EXISTS tenant_isolation ON secret_rotation_log"))
        await conn.execute(
            text(
                "CREATE POLICY tenant_isolation ON secret_rotation_log "
                "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
            )
        )
        await conn.exec_driver_sql(append_only_function_sql())
        await conn.exec_driver_sql(drop_trigger_sql("secret_rotation_log"))
        await conn.exec_driver_sql(create_trigger_sql("secret_rotation_log"))


async def _create_delivery_schedule(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    webhook_secret: str,
) -> DeliverySchedule:
    row = DeliverySchedule(
        tenant_id=tenant_id,
        name="Rotation schedule",
        description="secret rotation test",
        schedule_type="REPORT",
        source_definition_id=uuid.uuid4(),
        cron_expression="0 8 * * 1",
        timezone="UTC",
        recipients=[{"type": "webhook", "address": "https://example.com/hook"}],
        export_format="PDF",
        is_active=True,
        config={"webhook_secret": webhook_secret},
        created_by=created_by,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def _create_connector_instance(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    secret_ref: str,
) -> ExternalConnection:
    code = f"conn_{uuid.uuid4().hex[:8]}"
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnection,
        tenant_id=tenant_id,
        record_data={
            "connection_code": code,
            "connector_type": "zoho",
        },
        values={
            "organisation_id": tenant_id,
            "entity_id": None,
            "connector_type": "zoho",
            "connection_code": code,
            "connection_name": "Connector",
            "source_system_instance_id": f"source-{uuid.uuid4().hex[:8]}",
            "data_residency_region": "in",
            "pii_masking_enabled": True,
            "consent_reference": None,
            "pinned_connector_version": None,
            "connection_status": "active",
            "secret_ref": secret_ref,
            "created_by": created_by,
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=ExternalConnectionVersion,
        tenant_id=tenant_id,
        record_data={
            "connection_id": str(row.id),
            "version_no": 1,
            "version_token": uuid.uuid4().hex,
        },
        values={
            "connection_id": row.id,
            "version_no": 1,
            "version_token": uuid.uuid4().hex,
            "config_snapshot_json": {"api_key": secret_ref, "secret_ref": secret_ref},
            "supersedes_id": None,
            "status": "active",
            "created_by": created_by,
        },
    )
    await session.flush()
    return row


@pytest.mark.asyncio
async def test_rotation_log_create(async_session: AsyncSession, test_user) -> None:
    """Rotation audit log row can be inserted and read back."""
    await set_tenant_context(async_session, test_user.tenant_id)
    row = SecretRotationLog(
        tenant_id=test_user.tenant_id,
        secret_type="webhook_signing",
        resource_id=uuid.uuid4(),
        resource_type="delivery_schedule",
        rotated_by=test_user.id,
        rotation_method="manual",
        status="initiated",
        initiated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    async_session.add(row)
    await async_session.flush()

    fetched = (
        await async_session.execute(select(SecretRotationLog).where(SecretRotationLog.id == row.id))
    ).scalar_one()
    assert fetched.secret_type == "webhook_signing"
    assert fetched.status == "initiated"


@pytest.mark.asyncio
async def test_rotation_log_append_only(async_session: AsyncSession, test_user) -> None:
    """Rotation log table rejects UPDATE through append-only trigger."""
    await set_tenant_context(async_session, test_user.tenant_id)
    row = SecretRotationLog(
        tenant_id=test_user.tenant_id,
        secret_type="webhook_signing",
        rotation_method="manual",
        status="initiated",
        initiated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    async_session.add(row)
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE secret_rotation_log SET status = 'failed' WHERE id = :id"),
            {"id": str(row.id)},
        )
        await async_session.flush()


@pytest.mark.asyncio
async def test_rotation_log_platform_sentinel(async_session: AsyncSession) -> None:
    """Platform-level sentinel tenant entry can be inserted for SMTP events."""
    await set_tenant_context(async_session, PLATFORM_TENANT_ID)
    row = SecretRotationLog(
        tenant_id=PLATFORM_TENANT_ID,
        secret_type="smtp",
        rotation_method="manual",
        status="initiated",
        initiated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    async_session.add(row)
    await async_session.flush()

    fetched = (
        await async_session.execute(select(SecretRotationLog).where(SecretRotationLog.id == row.id))
    ).scalar_one()
    assert fetched.tenant_id == PLATFORM_TENANT_ID


@pytest.mark.asyncio
async def test_rotate_webhook_secret_generates_new_secret(async_session: AsyncSession, test_user) -> None:
    """Webhook secret rotation generates and stores a different secret."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="old-secret-1234",
    )

    old_secret = _read_webhook_secret(schedule.config)
    result = await rotate_webhook_secret(
        async_session,
        tenant_id=test_user.tenant_id,
        schedule_id=schedule.id,
        user_id=test_user.id,
    )

    refreshed = (
        await async_session.execute(
            select(DeliverySchedule).where(
                DeliverySchedule.tenant_id == test_user.tenant_id,
                DeliverySchedule.id == schedule.id,
            )
        )
    ).scalar_one()
    new_secret = _read_webhook_secret(refreshed.config)
    assert result["schedule_id"] == str(schedule.id)
    assert new_secret != old_secret


@pytest.mark.asyncio
async def test_rotate_webhook_secret_logs_rotation(async_session: AsyncSession, test_user) -> None:
    """Webhook secret rotation writes completed event in rotation log."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="old-1234",
    )

    await rotate_webhook_secret(async_session, test_user.tenant_id, schedule.id, test_user.id)

    logs = (
        await async_session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == test_user.tenant_id,
                SecretRotationLog.resource_id == schedule.id,
                SecretRotationLog.secret_type == "webhook_signing",
            )
        )
    ).scalars().all()
    assert any(entry.status == "completed" for entry in logs)


@pytest.mark.asyncio
async def test_rotate_webhook_secret_hint_is_last_4(async_session: AsyncSession, test_user) -> None:
    """Webhook completed event stores only the last-4 hint of the new secret."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="secret-old",
    )

    await rotate_webhook_secret(async_session, test_user.tenant_id, schedule.id, test_user.id)

    refreshed = (
        await async_session.execute(
            select(DeliverySchedule).where(
                DeliverySchedule.tenant_id == test_user.tenant_id,
                DeliverySchedule.id == schedule.id,
            )
        )
    ).scalar_one()
    current_secret = _read_webhook_secret(refreshed.config)

    completed = (
        await async_session.execute(
            select(SecretRotationLog)
            .where(
                SecretRotationLog.tenant_id == test_user.tenant_id,
                SecretRotationLog.resource_id == schedule.id,
                SecretRotationLog.secret_type == "webhook_signing",
                SecretRotationLog.status == "completed",
            )
            .order_by(SecretRotationLog.initiated_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert completed.new_secret_hint == current_secret[-4:]


@pytest.mark.asyncio
async def test_rotate_webhook_secret_wrong_tenant_raises(async_session: AsyncSession, test_user) -> None:
    """Webhook secret rotation rejects access from a different tenant context."""
    tenant_a = test_user.tenant_id
    tenant_b = uuid.uuid4()

    await set_tenant_context(async_session, tenant_a)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=tenant_a,
        created_by=test_user.id,
        webhook_secret="old-secret",
    )

    await set_tenant_context(async_session, tenant_b)
    with pytest.raises(LookupError):
        await rotate_webhook_secret(async_session, tenant_b, schedule.id, test_user.id)


@pytest.mark.asyncio
async def test_rotate_webhook_secret_is_zero_downtime(async_session: AsyncSession, test_user) -> None:
    """Webhook rotation writes new secret atomically so stored value is immediately usable."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="zero-downtime-old",
    )

    old_secret = _read_webhook_secret(schedule.config)
    result = await rotate_webhook_secret(async_session, test_user.tenant_id, schedule.id, test_user.id)

    refreshed = (
        await async_session.execute(
            select(DeliverySchedule).where(
                DeliverySchedule.tenant_id == test_user.tenant_id,
                DeliverySchedule.id == schedule.id,
            )
        )
    ).scalar_one()
    new_secret = _read_webhook_secret(refreshed.config)

    assert new_secret and new_secret != old_secret
    assert new_secret.endswith(str(result["hint"]))


@pytest.mark.asyncio
async def test_rotate_webhook_secret_idempotent_log(async_session: AsyncSession, test_user) -> None:
    """Two webhook rotations create two distinct completed audit events."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="rotate-twice-old",
    )

    await rotate_webhook_secret(async_session, test_user.tenant_id, schedule.id, test_user.id)
    await rotate_webhook_secret(async_session, test_user.tenant_id, schedule.id, test_user.id)

    completed_count = (
        await async_session.execute(
            select(func.count())
            .select_from(SecretRotationLog)
            .where(
                SecretRotationLog.tenant_id == test_user.tenant_id,
                SecretRotationLog.resource_id == schedule.id,
                SecretRotationLog.secret_type == "webhook_signing",
                SecretRotationLog.status == "completed",
            )
        )
    ).scalar_one()
    assert int(completed_count or 0) == 2


@pytest.mark.asyncio
async def test_rotate_erp_api_key_updates_key(async_session: AsyncSession, test_user) -> None:
    """ERP API key rotation appends a new connection version with the new key."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="old-test-key",
    )

    await rotate_erp_api_key(
        async_session,
        tenant_id=test_user.tenant_id,
        connector_instance_id=connector.id,
        new_api_key="new-test-key-xyz",
        user_id=test_user.id,
    )

    latest = (
        await async_session.execute(
            select(ExternalConnectionVersion)
            .where(
                ExternalConnectionVersion.tenant_id == test_user.tenant_id,
                ExternalConnectionVersion.connection_id == connector.id,
            )
            .order_by(ExternalConnectionVersion.version_no.desc())
            .limit(1)
        )
    ).scalar_one()
    snapshot = dict(latest.config_snapshot_json or {})
    assert _read_api_key(snapshot) == "new-test-key-xyz"


@pytest.mark.asyncio
async def test_rotate_erp_api_key_logs_rotation(async_session: AsyncSession, test_user) -> None:
    """ERP API key rotation writes completed audit entry."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="old-key-log",
    )

    await rotate_erp_api_key(
        async_session,
        tenant_id=test_user.tenant_id,
        connector_instance_id=connector.id,
        new_api_key="new-key-log",
        user_id=test_user.id,
    )

    logs = (
        await async_session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == test_user.tenant_id,
                SecretRotationLog.resource_id == connector.id,
                SecretRotationLog.secret_type == "erp_api_key",
            )
        )
    ).scalars().all()
    assert any(entry.status == "completed" for entry in logs)


@pytest.mark.asyncio
async def test_rotate_erp_api_key_rejects_empty_key(async_session: AsyncSession, test_user) -> None:
    """ERP API key rotation rejects empty input key."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="old-key",
    )

    with pytest.raises(ValueError):
        await rotate_erp_api_key(
            async_session,
            tenant_id=test_user.tenant_id,
            connector_instance_id=connector.id,
            new_api_key="",
            user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_rotate_erp_api_key_rejects_same_key(async_session: AsyncSession, test_user) -> None:
    """ERP API key rotation rejects same key as currently active key."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="same-key",
    )

    with pytest.raises(ValueError):
        await rotate_erp_api_key(
            async_session,
            tenant_id=test_user.tenant_id,
            connector_instance_id=connector.id,
            new_api_key="same-key",
            user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_rotate_erp_api_key_wrong_tenant_raises(async_session: AsyncSession, test_user) -> None:
    """ERP API key rotation rejects requests for a connector in another tenant."""
    tenant_a = test_user.tenant_id
    tenant_b = uuid.uuid4()

    await set_tenant_context(async_session, tenant_a)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=tenant_a,
        created_by=test_user.id,
        secret_ref="old-key-wrong-tenant",
    )

    await set_tenant_context(async_session, tenant_b)
    with pytest.raises(LookupError):
        await rotate_erp_api_key(
            async_session,
            tenant_id=tenant_b,
            connector_instance_id=connector.id,
            new_api_key="new-key",
            user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_rotate_erp_api_key_failed_status_on_error(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ERP API key rotation records failed status when version write raises."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="old-fail-key",
    )

    from financeops.modules.secret_rotation import service as rotation_service

    async def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("write-failed")

    monkeypatch.setattr(rotation_service.AuditWriter, "insert_financial_record", _boom)

    with pytest.raises(RuntimeError, match="write-failed"):
        await rotate_erp_api_key(
            async_session,
            tenant_id=test_user.tenant_id,
            connector_instance_id=connector.id,
            new_api_key="new-fail-key",
            user_id=test_user.id,
        )

    failed_entries = (
        await async_session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == test_user.tenant_id,
                SecretRotationLog.resource_id == connector.id,
                SecretRotationLog.secret_type == "erp_api_key",
                SecretRotationLog.status == "failed",
            )
        )
    ).scalars().all()
    assert failed_entries
    assert any("write-failed" in str(entry.failure_reason or "") for entry in failed_entries)


@pytest.mark.asyncio
async def test_rotate_smtp_validates_connection(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP rotation succeeds when SMTP probe connection/login succeeds."""
    await set_tenant_context(async_session, test_user.tenant_id)

    from financeops.modules.secret_rotation import service as rotation_service

    monkeypatch.setattr(rotation_service, "probe_smtp_connection", AsyncMock(return_value=None))

    result = await rotate_smtp_credentials(
        async_session,
        new_smtp_host="smtp.example.com",
        new_smtp_user="user@example.com",
        new_smtp_password="secret-1234",
        user_id=test_user.id,
    )
    assert result["status"] == "verified"


@pytest.mark.asyncio
async def test_rotate_smtp_logs_rotation(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP rotation writes completed event under platform sentinel tenant."""
    await set_tenant_context(async_session, test_user.tenant_id)

    from financeops.modules.secret_rotation import service as rotation_service

    monkeypatch.setattr(rotation_service, "probe_smtp_connection", AsyncMock(return_value=None))

    await rotate_smtp_credentials(
        async_session,
        new_smtp_host="smtp.example.com",
        new_smtp_user="user@example.com",
        new_smtp_password="secret-1234",
        user_id=test_user.id,
    )

    await set_tenant_context(async_session, PLATFORM_TENANT_ID)
    rows = (
        await async_session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == PLATFORM_TENANT_ID,
                SecretRotationLog.secret_type == "smtp",
                SecretRotationLog.status == "completed",
            )
        )
    ).scalars().all()
    assert rows


@pytest.mark.asyncio
async def test_rotate_smtp_fails_on_bad_credentials(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP rotation raises when SMTP authentication fails and logs failed event."""
    await set_tenant_context(async_session, test_user.tenant_id)

    from financeops.modules.secret_rotation import service as rotation_service

    monkeypatch.setattr(
        rotation_service,
        "probe_smtp_connection",
        AsyncMock(side_effect=RuntimeError("auth failed")),
    )

    with pytest.raises(RuntimeError):
        await rotate_smtp_credentials(
            async_session,
            new_smtp_host="smtp.example.com",
            new_smtp_user="user@example.com",
            new_smtp_password="bad-secret",
            user_id=test_user.id,
        )

    await set_tenant_context(async_session, PLATFORM_TENANT_ID)
    failed_rows = (
        await async_session.execute(
            select(SecretRotationLog).where(
                SecretRotationLog.tenant_id == PLATFORM_TENANT_ID,
                SecretRotationLog.secret_type == "smtp",
                SecretRotationLog.status == "failed",
            )
        )
    ).scalars().all()
    assert failed_rows


@pytest.mark.asyncio
async def test_rotate_smtp_returns_action_required(
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP rotation success response includes operational action guidance."""
    await set_tenant_context(async_session, test_user.tenant_id)

    from financeops.modules.secret_rotation import service as rotation_service

    monkeypatch.setattr(rotation_service, "probe_smtp_connection", AsyncMock(return_value=None))

    result = await rotate_smtp_credentials(
        async_session,
        new_smtp_host="smtp.example.com",
        new_smtp_user="user@example.com",
        new_smtp_password="secret-1234",
        user_id=test_user.id,
    )
    assert "action_required" in result


@pytest.mark.asyncio
async def test_rotate_webhook_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Webhook rotation endpoint returns success payload including secret hint."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="endpoint-old-secret",
    )

    response = await async_client.post(
        f"/api/v1/secrets/rotate/webhook/{schedule.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["schedule_id"] == str(schedule.id)
    assert payload["hint"]


@pytest.mark.asyncio
async def test_rotate_webhook_endpoint_404(async_client: AsyncClient, test_access_token: str) -> None:
    """Webhook rotation endpoint returns 404 for unknown schedule id."""
    response = await async_client.post(
        f"/api/v1/secrets/rotate/webhook/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rotate_erp_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """ERP rotation endpoint accepts a valid key and returns success."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="endpoint-old-key",
    )

    response = await async_client.post(
        f"/api/v1/secrets/rotate/erp/{connector.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"new_api_key": "endpoint-new-key"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["connector_id"] == str(connector.id)


@pytest.mark.asyncio
async def test_rotate_erp_endpoint_empty_key(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """ERP rotation endpoint rejects empty new_api_key with 422."""
    await set_tenant_context(async_session, test_user.tenant_id)
    connector = await _create_connector_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        secret_ref="endpoint-empty-key-old",
    )

    response = await async_client.post(
        f"/api/v1/secrets/rotate/erp/{connector.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"new_api_key": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rotation_log_endpoint(async_client: AsyncClient, test_access_token: str) -> None:
    """Rotation log endpoint returns list payload for current tenant."""
    response = await async_client.get(
        "/api/v1/secrets/rotation-log",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_rotation_log_endpoint_filtered(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Rotation log endpoint secret_type filter returns only matching entries."""
    await set_tenant_context(async_session, test_user.tenant_id)
    async_session.add_all(
        [
            SecretRotationLog(
                tenant_id=test_user.tenant_id,
                secret_type="webhook_signing",
                resource_id=uuid.uuid4(),
                resource_type="delivery_schedule",
                rotated_by=test_user.id,
                rotation_method="manual",
                status="completed",
                initiated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
            SecretRotationLog(
                tenant_id=test_user.tenant_id,
                secret_type="erp_api_key",
                resource_id=uuid.uuid4(),
                resource_type="erp_connector",
                rotated_by=test_user.id,
                rotation_method="manual",
                status="completed",
                initiated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
        ]
    )
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/secrets/rotation-log?secret_type=webhook_signing",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload
    assert all(entry["secret_type"] == "webhook_signing" for entry in payload)
