from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from financeops.modules.payment.application.webhook_service import WebhookService
from financeops.modules.payment.domain.enums import PaymentProvider


class _NestedTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeProvider:
    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        return True

    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]:
        return "invoice.paid", {"provider_event_id": payload.get("id", "evt_1")}


@pytest.mark.asyncio
async def test_handle_webhook_skips_duplicate_event(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.begin_nested = Mock(return_value=_NestedTransaction())
    insert_mock = AsyncMock()
    route_mock = AsyncMock()

    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.get_provider",
        lambda provider: _FakeProvider(),
    )
    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.AuditWriter.insert_financial_record",
        insert_mock,
    )

    service = WebhookService(session)
    service._route_event = route_mock

    async def _raise_duplicate(*args, **kwargs):
        raise IntegrityError("insert", {}, Exception("duplicate webhook"))

    insert_mock.side_effect = _raise_duplicate
    await service.handle_webhook(
        provider=PaymentProvider.STRIPE,
        payload=json.dumps({"id": "evt_duplicate"}).encode("utf-8"),
        signature="sig",
        secret="secret",
        tenant_id=uuid.uuid4(),
    )
    insert_mock.assert_awaited_once()
    route_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_webhook_inserts_processed_record(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.begin_nested = Mock(return_value=_NestedTransaction())
    insert_mock = AsyncMock()
    route_mock = AsyncMock()

    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.get_provider",
        lambda provider: _FakeProvider(),
    )
    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.AuditWriter.insert_financial_record",
        insert_mock,
    )

    service = WebhookService(session)
    service._route_event = route_mock
    await service.handle_webhook(
        provider=PaymentProvider.RAZORPAY,
        payload=json.dumps({"id": "evt_ok"}).encode("utf-8"),
        signature="sig",
        secret="secret",
        tenant_id=uuid.uuid4(),
    )
    insert_mock.assert_awaited_once()
    route_mock.assert_awaited_once()
