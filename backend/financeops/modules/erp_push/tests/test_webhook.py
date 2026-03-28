from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from financeops.db.models.erp_webhook import CanonicalWebhookEventType
from financeops.modules.erp_push.application.webhook_processor import (
    process_webhook_event,
)
from financeops.modules.erp_push.application.webhook_service import (
    _extract_message_id,
    _fallback_message_id,
    _normalise_event_type,
    _verify_signature,
    ingest_webhook,
)
from financeops.modules.erp_push.domain.webhook_verifier import (
    verify_qbo_webhook_signature,
    verify_tally_webhook,
    verify_zoho_webhook_signature,
)


class TestVerifyZohoWebhookSignature:
    def _token(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    def test_valid_signature(self) -> None:
        body = b'{"event_type":"invoice.created"}'
        secret = "zoho_secret"
        token = self._token(body, secret)
        assert verify_zoho_webhook_signature(
            raw_body=body,
            received_token=token,
            webhook_secret=secret,
        )

    def test_invalid_signature(self) -> None:
        assert not verify_zoho_webhook_signature(
            raw_body=b"payload",
            received_token="wrong",
            webhook_secret="secret",
        )

    def test_missing_token_or_secret(self) -> None:
        assert not verify_zoho_webhook_signature(
            raw_body=b"payload",
            received_token="",
            webhook_secret="secret",
        )
        assert not verify_zoho_webhook_signature(
            raw_body=b"payload",
            received_token="token",
            webhook_secret="",
        )


class TestVerifyQBOWebhookSignature:
    def _payload_hash(self, body: bytes, token: str) -> str:
        digest = hmac.new(token.encode("utf-8"), body, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def test_valid_signature(self) -> None:
        body = b'{"eventNotifications":[]}'
        token = "qbo_token"
        received = self._payload_hash(body, token)
        assert verify_qbo_webhook_signature(
            raw_body=body,
            received_hash=received,
            verifier_token=token,
        )

    def test_invalid_signature(self) -> None:
        assert not verify_qbo_webhook_signature(
            raw_body=b"payload",
            received_hash="invalid",
            verifier_token="qbo_token",
        )

    def test_missing_hash_or_token(self) -> None:
        assert not verify_qbo_webhook_signature(
            raw_body=b"payload",
            received_hash="",
            verifier_token="qbo_token",
        )
        assert not verify_qbo_webhook_signature(
            raw_body=b"payload",
            received_hash="abc",
            verifier_token="",
        )


class TestVerifyTallyWebhook:
    def test_always_true(self) -> None:
        assert verify_tally_webhook(raw_body=b"anything", headers={})


class TestWebhookHelpers:
    def test_normalise_known_types(self) -> None:
        assert (
            _normalise_event_type("ZOHO", "invoice.created")
            == CanonicalWebhookEventType.INVOICE_CREATED
        )
        assert (
            _normalise_event_type("QBO", "Invoice")
            == CanonicalWebhookEventType.INVOICE_UPDATED
        )

    def test_normalise_unknown_type(self) -> None:
        assert (
            _normalise_event_type("ZOHO", "unknown.event")
            == CanonicalWebhookEventType.UNKNOWN
        )

    def test_extract_message_id_zoho(self) -> None:
        payload = {"event_id": "evt_123", "event_type": "invoice.created"}
        assert _extract_message_id("ZOHO", payload, {}) == "evt_123"

    def test_extract_message_id_qbo(self) -> None:
        payload = {
            "eventNotifications": [
                {
                    "dataChangeEvent": {
                        "entities": [
                            {"id": "INV-1", "lastUpdated": "2026-03-01T10:00:00Z"}
                        ]
                    }
                }
            ]
        }
        assert "INV-1" in _extract_message_id("QBO", payload, {})

    def test_fallback_message_id_deterministic(self) -> None:
        payload = {"k": "v"}
        assert _fallback_message_id(payload) == _fallback_message_id(payload)

    def test_verify_signature_dispatch(self) -> None:
        body = b'{"event_type":"invoice.created"}'
        secret = "zoho_secret"
        token = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert _verify_signature(
            connector_type="ZOHO",
            raw_body=body,
            headers={"x-zoho-webhook-token": token},
            webhook_secret=secret,
        )


class TestIngestWebhook:
    @pytest.mark.asyncio
    async def test_new_event_inserted_and_enqueued(self) -> None:
        tenant_id = uuid.uuid4()
        event = SimpleNamespace(id=uuid.uuid4())
        db = AsyncMock()
        initial_result = MagicMock()
        initial_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=initial_result)

        with (
            patch(
                "financeops.modules.erp_push.application.webhook_service."
                "AuditWriter.insert_financial_record",
                new_callable=AsyncMock,
                return_value=event,
            ) as insert_mock,
            patch(
                "financeops.modules.erp_push.application.webhook_service."
                "_enqueue_webhook_processing"
            ) as enqueue_mock,
        ):
            result = await ingest_webhook(
                db,
                tenant_id=tenant_id,
                connector_type="ZOHO",
                raw_body=b'{"event_id":"evt_1","event_type":"invoice.created"}',
                headers={"x-zoho-webhook-token": "bad"},
                payload={"event_id": "evt_1", "event_type": "invoice.created"},
                webhook_secret="secret",
            )

        assert result is event
        assert insert_mock.await_count == 1
        enqueue_mock.assert_called_once()
        assert db.flush.await_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_returns_existing(self) -> None:
        tenant_id = uuid.uuid4()
        existing = SimpleNamespace(id=uuid.uuid4())
        db = AsyncMock()
        duplicate_result = MagicMock()
        duplicate_result.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=duplicate_result)

        with patch(
            "financeops.modules.erp_push.application.webhook_service."
            "AuditWriter.insert_financial_record",
            new_callable=AsyncMock,
        ) as insert_mock:
            result = await ingest_webhook(
                db,
                tenant_id=tenant_id,
                connector_type="QBO",
                raw_body=b"{}",
                headers={},
                payload={},
                webhook_secret="secret",
            )

        assert result is existing
        insert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_integrity_error_race_returns_existing(self) -> None:
        tenant_id = uuid.uuid4()
        existing = SimpleNamespace(id=uuid.uuid4())
        db = AsyncMock()

        first_select = MagicMock()
        first_select.scalar_one_or_none.return_value = None
        second_select = MagicMock()
        second_select.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(side_effect=[first_select, second_select])

        with patch(
            "financeops.modules.erp_push.application.webhook_service."
            "AuditWriter.insert_financial_record",
            new_callable=AsyncMock,
            side_effect=IntegrityError("insert", {}, Exception("duplicate")),
        ):
            result = await ingest_webhook(
                db,
                tenant_id=tenant_id,
                connector_type="ZOHO",
                raw_body=b'{"event_id":"evt_2"}',
                headers={},
                payload={"event_id": "evt_2"},
                webhook_secret="secret",
            )

        assert result is existing
        assert db.rollback.await_count == 1


class TestWebhookProcessor:
    @pytest.mark.asyncio
    async def test_already_processed_short_circuit(self) -> None:
        tenant_id = uuid.uuid4()
        event_id = uuid.uuid4()
        event = SimpleNamespace(
            id=event_id,
            tenant_id=tenant_id,
            processed=True,
        )
        db = AsyncMock()
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = event
        db.execute = AsyncMock(return_value=select_result)

        result = await process_webhook_event(
            db,
            event_id=event_id,
            tenant_id=tenant_id,
            canonical_event_type=CanonicalWebhookEventType.PAYMENT_RECEIVED,
        )

        assert result["outcome"] == "ALREADY_PROCESSED"

    @pytest.mark.asyncio
    async def test_unknown_event_dead_lettered(self) -> None:
        tenant_id = uuid.uuid4()
        event_id = uuid.uuid4()
        event = SimpleNamespace(
            id=event_id,
            tenant_id=tenant_id,
            connector_type="ZOHO",
            event_type="unexpected.event",
            payload={},
            processed=False,
            dead_lettered=False,
            dead_letter_reason=None,
            processing_error=None,
            processed_at=None,
        )
        db = AsyncMock()
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = event
        db.execute = AsyncMock(return_value=select_result)

        result = await process_webhook_event(
            db,
            event_id=event_id,
            tenant_id=tenant_id,
            canonical_event_type=CanonicalWebhookEventType.UNKNOWN,
        )

        assert result["outcome"] == "DEAD_LETTERED"
        assert event.dead_lettered is True
        assert event.dead_letter_reason is not None
        assert db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_account_event_marks_processed(self) -> None:
        tenant_id = uuid.uuid4()
        event_id = uuid.uuid4()
        event = SimpleNamespace(
            id=event_id,
            tenant_id=tenant_id,
            connector_type="QBO",
            event_type="Account",
            payload={"account_id": "ACC-1"},
            processed=False,
            dead_lettered=False,
            dead_letter_reason=None,
            processing_error=None,
            processed_at=None,
        )
        db = AsyncMock()
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = event
        update_result = MagicMock()
        db.execute = AsyncMock(side_effect=[select_result, update_result])

        result = await process_webhook_event(
            db,
            event_id=event_id,
            tenant_id=tenant_id,
            canonical_event_type=CanonicalWebhookEventType.ACCOUNT_UPDATED,
        )

        assert result["outcome"] == "PROCESSED"
        assert event.processed is True
        assert db.commit.await_count == 1


class TestCanonicalWebhookEventTypes:
    def test_constants_complete(self) -> None:
        assert CanonicalWebhookEventType.PAYMENT_RECEIVED in CanonicalWebhookEventType.ALL
        assert CanonicalWebhookEventType.INVOICE_UPDATED in CanonicalWebhookEventType.ALL
        assert CanonicalWebhookEventType.UNKNOWN in CanonicalWebhookEventType.ALL
        assert len(CanonicalWebhookEventType.ALL) == 10
