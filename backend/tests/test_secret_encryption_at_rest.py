from __future__ import annotations

import hmac
import json
import uuid
from datetime import UTC, datetime
from hashlib import sha256

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import decrypt_field, encrypt_field
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.erp_sync import ExternalConnection
from financeops.db.models.scheduled_delivery import DeliverySchedule
from financeops.db.rls import set_tenant_context
from financeops.modules.secret_rotation.models import SecretRotationLog
from financeops.modules.scheduled_delivery.application.delivery_service import DeliveryService
from financeops.modules.payment.application.entitlement_service import EntitlementService


@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_secret_rotation_schema(engine) -> None:
    """Ensure secret_rotation_log table and trigger exist before secret-rotation endpoint tests."""
    from sqlalchemy import text

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
        name="Encryption schedule",
        description="secret encryption test",
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


@pytest.mark.asyncio
async def test_webhook_secret_not_stored_plaintext(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """After rotation, webhook secret is encrypted at rest and round-trips on decrypt."""
    await set_tenant_context(async_session, test_user.tenant_id)
    schedule = await _create_delivery_schedule(
        async_session,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        webhook_secret="plaintext-webhook-secret-1234",
    )

    response = await async_client.post(
        f"/api/v1/secrets/rotate/webhook/{schedule.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    new_secret_hint = response.json()["data"]["hint"]

    await set_tenant_context(async_session, test_user.tenant_id)
    refreshed = (
        await async_session.execute(
            select(DeliverySchedule)
            .execution_options(populate_existing=True)
            .where(
                DeliverySchedule.tenant_id == test_user.tenant_id,
                DeliverySchedule.id == schedule.id,
            )
        )
    ).scalar_one()
    config_json = json.dumps(refreshed.config or {})

    assert "webhook_secret_enc" in config_json
    assert '"webhook_secret"' not in config_json
    assert new_secret_hint not in config_json

    decrypted = decrypt_field(str((refreshed.config or {}).get("webhook_secret_enc")))
    assert decrypted[-4:] == new_secret_hint


@pytest.mark.asyncio
async def test_erp_secret_ref_not_stored_plaintext(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ERP connection secret_ref is encrypted at rest and decrypts back to source value."""
    from financeops.api import deps as api_deps

    class _FakeRedis:
        async def get(self, key: str):  # type: ignore[no-untyped-def]
            _ = key
            return None

        async def setex(self, key: str, ttl: int, value: str):  # type: ignore[no-untyped-def]
            _ = (key, ttl, value)
            return True

    monkeypatch.setattr(api_deps, "_redis_pool", _FakeRedis())
    await set_tenant_context(async_session, test_user.tenant_id)
    await EntitlementService(async_session).create_tenant_override_entitlement(
        tenant_id=test_user.tenant_id,
        feature_name="erp_integration",
        access_type="boolean",
        effective_limit=1,
        actor_user_id=test_user.id,
        metadata={"reason": "secret_encryption_test"},
    )
    await async_session.flush()

    plain_api_key = "test-api-key-sprint1-fix"
    connection_code = f"enc-{uuid.uuid4().hex[:8]}"
    payload = {
        "connector_type": "zoho",
        "connection_code": connection_code,
        "connection_name": "Encrypted Connection",
        "organisation_id": str(test_user.tenant_id),
        "client_id": "zoho-client-id",
        "client_secret": "zoho-client-secret",
        "organization_id": "zoho-org-encrypted",
        "secret_ref": plain_api_key,
    }
    response = await async_client.post(
        "/api/v1/erp-sync/connections",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json=payload,
    )
    assert response.status_code == 200
    connection_id = uuid.UUID(response.json()["data"]["connection_id"])

    await set_tenant_context(async_session, test_user.tenant_id)
    row = (
        await async_session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == test_user.tenant_id,
                ExternalConnection.id == connection_id,
            )
        )
    ).scalar_one()
    assert row.secret_ref is not None
    assert row.secret_ref != plain_api_key
    decrypted_payload = json.loads(decrypt_field(row.secret_ref))
    assert decrypted_payload.get("api_key") == plain_api_key
    assert decrypted_payload.get("client_id") == "zoho-client-id"
    assert decrypted_payload.get("client_secret") == "zoho-client-secret"
    assert decrypted_payload.get("organization_id") == "zoho-org-encrypted"


@pytest.mark.asyncio
async def test_zoho_connection_creation_requires_organization_id(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.api import deps as api_deps

    class _FakeRedis:
        async def get(self, key: str):  # type: ignore[no-untyped-def]
            _ = key
            return None

        async def setex(self, key: str, ttl: int, value: str):  # type: ignore[no-untyped-def]
            _ = (key, ttl, value)
            return True

    monkeypatch.setattr(api_deps, "_redis_pool", _FakeRedis())
    await set_tenant_context(async_session, test_user.tenant_id)
    await EntitlementService(async_session).create_tenant_override_entitlement(
        tenant_id=test_user.tenant_id,
        feature_name="erp_integration",
        access_type="boolean",
        effective_limit=1,
        actor_user_id=test_user.id,
        metadata={"reason": "zoho_org_id_missing_test"},
    )
    await async_session.flush()

    create_response = await async_client.post(
        "/api/v1/erp-sync/connections",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "connector_type": "zoho",
            "connection_code": f"zoho-{uuid.uuid4().hex[:8]}",
            "connection_name": "Zoho Missing Org",
            "organisation_id": str(test_user.tenant_id),
            "client_id": "client-id",
            "client_secret": "client-secret",
        },
    )
    assert create_response.status_code == 422
    payload = create_response.json()["error"]
    assert payload["code"] == "validation_error"
    assert "organization_id" in payload["message"]


@pytest.mark.asyncio
async def test_webhook_hmac_signing_works_after_encryption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook signing uses decrypted secret from encrypted config and produces valid HMAC."""
    secret = "rotation-secret-value-9999"
    encrypted_secret = encrypt_field(secret)
    schedule = DeliverySchedule(
        tenant_id=uuid.uuid4(),
        name="Schedule",
        description="",
        schedule_type="REPORT",
        source_definition_id=uuid.uuid4(),
        cron_expression="0 8 * * 1",
        timezone="UTC",
        recipients=[],
        export_format="PDF",
        is_active=True,
        config={"webhook_secret_enc": encrypted_secret},
        created_by=uuid.uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    async def _fake_post_bytes(*, url: str, body: bytes, headers: dict[str, str], timeout: float = 30.0):  # type: ignore[no-untyped-def]
        _ = timeout
        captured["url"] = url
        captured["content"] = body
        captured["headers"] = headers
        return _FakeResponse()

    from financeops.modules.scheduled_delivery.application import delivery_service as delivery_service_module

    monkeypatch.setattr(delivery_service_module, "post_bytes", _fake_post_bytes)

    service = DeliveryService()
    resolved_secret = service._webhook_secret(schedule)
    assert resolved_secret == secret

    payload = {"schedule_id": str(uuid.uuid4()), "event": "delivered"}
    await service._dispatch_webhook(
        url="https://example.com/hook",
        payload=payload,
        secret=resolved_secret,
    )

    assert captured.get("url") == "https://example.com/hook"
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = captured["headers"]
    assert isinstance(headers, dict)
    signature = headers.get("X-Finqor-Signature")
    assert signature is not None

    expected = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    assert signature == f"sha256={expected}"
