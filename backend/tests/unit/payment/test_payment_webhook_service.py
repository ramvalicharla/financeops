from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.modules.payment.application.webhook_service import WebhookService
from financeops.modules.payment.domain.enums import PaymentProvider


class _ExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeProvider:
    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        return True

    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]:
        return "invoice.paid", {"provider_event_id": payload.get("id", "evt_1")}


@pytest.mark.asyncio
async def test_handle_webhook_skips_duplicate_event(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ExecuteResult(SimpleNamespace(id=uuid.uuid4())))
    insert_mock = AsyncMock()

    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.get_provider",
        lambda provider: _FakeProvider(),
    )
    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.AuditWriter.insert_financial_record",
        insert_mock,
    )

    service = WebhookService(session)
    await service.handle_webhook(
        provider=PaymentProvider.STRIPE,
        payload=json.dumps({"id": "evt_duplicate"}).encode("utf-8"),
        signature="sig",
        secret="secret",
        tenant_id=uuid.uuid4(),
    )
    insert_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_webhook_inserts_processed_record(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ExecuteResult(None))
    insert_mock = AsyncMock()

    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.get_provider",
        lambda provider: _FakeProvider(),
    )
    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.AuditWriter.insert_financial_record",
        insert_mock,
    )

    service = WebhookService(session)
    await service.handle_webhook(
        provider=PaymentProvider.RAZORPAY,
        payload=json.dumps({"id": "evt_ok"}).encode("utf-8"),
        signature="sig",
        secret="secret",
        tenant_id=uuid.uuid4(),
    )
    insert_mock.assert_awaited_once()

