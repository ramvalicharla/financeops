from __future__ import annotations

import hmac
import json
import uuid
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from financeops.core.security import encrypt_field
from financeops.db.models.scheduled_delivery import DeliverySchedule
from financeops.modules.scheduled_delivery.application.delivery_service import DeliveryService
from financeops.modules.scheduled_delivery.domain.exceptions import DeliveryConfigError


def _schedule_with_secret(secret: str | None) -> DeliverySchedule:
    encrypted_secret = encrypt_field(secret) if secret else None
    return DeliverySchedule(
        tenant_id=uuid.uuid4(),
        name="Webhook Schedule",
        description="scheduled delivery webhook test",
        schedule_type="REPORT",
        source_definition_id=uuid.uuid4(),
        cron_expression="0 8 * * 1",
        timezone="UTC",
        recipients=[{"type": "webhook", "address": "https://example.com/hook"}],
        export_format="PDF",
        is_active=True,
        webhook_secret=encrypted_secret,
        config={"webhook_secret_enc": encrypted_secret} if encrypted_secret else {},
        created_by=uuid.uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_webhook_delivery_includes_x_finqor_signature_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    async def _fake_post_bytes(*, url: str, body: bytes, headers: dict[str, str], timeout: float = 30.0):  # type: ignore[no-untyped-def]
        _ = timeout
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        return _FakeResponse()

    from financeops.modules.scheduled_delivery.application import delivery_service as delivery_service_module

    monkeypatch.setattr(delivery_service_module, "post_bytes", _fake_post_bytes)

    service = DeliveryService()
    schedule = _schedule_with_secret("header-secret-1234")
    payload = {"schedule_id": str(schedule.id or uuid.uuid4()), "event": "delivered"}

    await service._dispatch_webhook(
        url="https://example.com/hook",
        payload=payload,
        secret=service._webhook_secret(schedule),
    )

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert "X-Finqor-Signature" in headers


@pytest.mark.asyncio
async def test_webhook_signature_is_valid_hmac_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    async def _fake_post_bytes(*, url: str, body: bytes, headers: dict[str, str], timeout: float = 30.0):  # type: ignore[no-untyped-def]
        _ = (url, timeout)
        captured["body"] = body
        captured["headers"] = headers
        return _FakeResponse()

    from financeops.modules.scheduled_delivery.application import delivery_service as delivery_service_module

    monkeypatch.setattr(delivery_service_module, "post_bytes", _fake_post_bytes)

    secret = "valid-hmac-secret-4321"
    service = DeliveryService()
    schedule = _schedule_with_secret(secret)
    payload = {"schedule_id": str(schedule.id or uuid.uuid4()), "event": "delivered"}

    await service._dispatch_webhook(
        url="https://example.com/hook",
        payload=payload,
        secret=service._webhook_secret(schedule),
    )

    headers = captured["headers"]
    assert isinstance(headers, dict)
    signature = headers.get("X-Finqor-Signature")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    assert signature == f"sha256={expected}"


@pytest.mark.asyncio
async def test_webhook_delivery_raises_if_no_secret_configured() -> None:
    service = DeliveryService()
    schedule = _schedule_with_secret(None)

    with pytest.raises(DeliveryConfigError, match="Webhook secret not configured"):
        await service._dispatch_webhook(
            url="https://example.com/hook",
            payload={"schedule_id": str(schedule.id or uuid.uuid4())},
            secret=service._webhook_secret(schedule),
        )


@pytest.mark.asyncio
async def test_recipient_can_verify_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    async def _fake_post_bytes(*, url: str, body: bytes, headers: dict[str, str], timeout: float = 30.0):  # type: ignore[no-untyped-def]
        _ = (url, timeout)
        captured["body"] = body
        captured["headers"] = headers
        return _FakeResponse()

    from financeops.modules.scheduled_delivery.application import delivery_service as delivery_service_module

    monkeypatch.setattr(delivery_service_module, "post_bytes", _fake_post_bytes)

    secret = "recipient-verify-secret"
    service = DeliveryService()
    schedule = _schedule_with_secret(secret)
    payload = {"schedule_id": str(schedule.id or uuid.uuid4()), "event": "delivered"}

    await service._dispatch_webhook(
        url="https://example.com/hook",
        payload=payload,
        secret=service._webhook_secret(schedule),
    )

    headers = captured["headers"]
    assert isinstance(headers, dict)
    signature = str(headers["X-Finqor-Signature"])
    body = captured["body"]
    assert isinstance(body, bytes)
    expected = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    assert signature == f"sha256={expected}"
