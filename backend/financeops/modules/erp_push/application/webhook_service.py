from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.erp_webhook import CanonicalWebhookEventType, ErpWebhookEvent
from financeops.modules.erp_push.domain.webhook_verifier import (
    verify_qbo_webhook_signature,
    verify_tally_webhook,
    verify_zoho_webhook_signature,
)
from financeops.services.audit_writer import AuditWriter

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


_ZOHO_EVENT_MAP: dict[str, str] = {
    "invoice.created": CanonicalWebhookEventType.INVOICE_CREATED,
    "invoice.updated": CanonicalWebhookEventType.INVOICE_UPDATED,
    "payment.received": CanonicalWebhookEventType.PAYMENT_RECEIVED,
    "contact.created": CanonicalWebhookEventType.VENDOR_CREATED,
    "contact.updated": CanonicalWebhookEventType.VENDOR_UPDATED,
    "chartofaccounts.created": CanonicalWebhookEventType.ACCOUNT_CREATED,
    "chartofaccounts.updated": CanonicalWebhookEventType.ACCOUNT_UPDATED,
    "journals.created": CanonicalWebhookEventType.JOURNAL_CREATED,
    "journals.updated": CanonicalWebhookEventType.JOURNAL_UPDATED,
}

_QBO_EVENT_MAP: dict[str, str] = {
    "Invoice": CanonicalWebhookEventType.INVOICE_UPDATED,
    "Payment": CanonicalWebhookEventType.PAYMENT_RECEIVED,
    "Vendor": CanonicalWebhookEventType.VENDOR_UPDATED,
    "Account": CanonicalWebhookEventType.ACCOUNT_UPDATED,
    "JournalEntry": CanonicalWebhookEventType.JOURNAL_UPDATED,
}


def _normalise_event_type(connector_type: str, raw_event_type: str) -> str:
    normalised = connector_type.upper()
    if normalised == "ZOHO":
        return _ZOHO_EVENT_MAP.get(raw_event_type.lower(), CanonicalWebhookEventType.UNKNOWN)
    if normalised in {"QBO", "QUICKBOOKS"}:
        return _QBO_EVENT_MAP.get(raw_event_type, CanonicalWebhookEventType.UNKNOWN)
    return CanonicalWebhookEventType.UNKNOWN


def _fallback_message_id(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:64]


def _extract_message_id(
    connector_type: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> str:
    _ = headers
    normalised = connector_type.upper()
    if normalised == "ZOHO":
        return str(payload.get("event_id") or payload.get("id") or _fallback_message_id(payload))

    if normalised in {"QBO", "QUICKBOOKS"}:
        notifications = payload.get("eventNotifications", [])
        if isinstance(notifications, list) and notifications:
            first_notification = notifications[0]
            if isinstance(first_notification, dict):
                entities = first_notification.get("dataChangeEvent", {}).get("entities", [])
                if isinstance(entities, list) and entities:
                    entity = entities[0]
                    if isinstance(entity, dict):
                        entity_id = str(entity.get("id") or "")
                        updated = str(entity.get("lastUpdated") or "")
                        if entity_id or updated:
                            return f"qbo_{entity_id}_{updated}"
        return _fallback_message_id(payload)

    if normalised == "TALLY":
        return str(payload.get("voucher_number") or _fallback_message_id(payload))

    return _fallback_message_id(payload)


def _extract_event_type(connector_type: str, payload: dict[str, Any]) -> str:
    normalised = connector_type.upper()
    if normalised == "ZOHO":
        return str(payload.get("event_type") or "unknown")
    if normalised in {"QBO", "QUICKBOOKS"}:
        notifications = payload.get("eventNotifications", [])
        if isinstance(notifications, list) and notifications:
            first_notification = notifications[0]
            if isinstance(first_notification, dict):
                entities = first_notification.get("dataChangeEvent", {}).get("entities", [])
                if isinstance(entities, list) and entities:
                    entity = entities[0]
                    if isinstance(entity, dict):
                        return str(entity.get("name") or "unknown")
        return "unknown"
    if normalised == "TALLY":
        return str(payload.get("voucher_type") or "unknown")
    return "unknown"


def _verify_signature(
    *,
    connector_type: str,
    raw_body: bytes,
    headers: dict[str, str],
    webhook_secret: str | None,
) -> bool:
    normalised = connector_type.upper()
    if normalised == "ZOHO":
        return verify_zoho_webhook_signature(
            raw_body=raw_body,
            received_token=str(headers.get("x-zoho-webhook-token") or ""),
            webhook_secret=str(webhook_secret or ""),
        )
    if normalised in {"QBO", "QUICKBOOKS"}:
        return verify_qbo_webhook_signature(
            raw_body=raw_body,
            received_hash=str(headers.get("intuit-payload-hash") or ""),
            verifier_token=str(webhook_secret or ""),
        )
    if normalised == "TALLY":
        return verify_tally_webhook(raw_body=raw_body, headers=headers)
    return False


async def ingest_webhook(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector_type: str,
    raw_body: bytes,
    headers: dict[str, str],
    payload: dict[str, Any],
    webhook_secret: str | None = None,
) -> ErpWebhookEvent:
    normalised_connector = connector_type.upper()
    signature_verified = _verify_signature(
        connector_type=normalised_connector,
        raw_body=raw_body,
        headers=headers,
        webhook_secret=webhook_secret,
    )
    if not signature_verified and normalised_connector != "TALLY":
        logger.warning(
            "ERP webhook signature verification failed",
            extra={
                "tenant_id": str(tenant_id),
                "connector_type": normalised_connector,
            },
        )

    message_id = _extract_message_id(normalised_connector, payload, headers)
    raw_event_type = _extract_event_type(normalised_connector, payload)
    canonical_event_type = _normalise_event_type(normalised_connector, raw_event_type)

    duplicate_stmt = select(ErpWebhookEvent).where(
        ErpWebhookEvent.tenant_id == tenant_id,
        ErpWebhookEvent.connector_type == normalised_connector,
        ErpWebhookEvent.message_id == message_id,
    )
    duplicate = (await db.execute(duplicate_stmt)).scalar_one_or_none()
    if duplicate is not None:
        logger.info(
            "ERP webhook duplicate ignored",
            extra={
                "tenant_id": str(tenant_id),
                "connector_type": normalised_connector,
                "message_id": message_id,
            },
        )
        return duplicate

    try:
        event = await AuditWriter.insert_financial_record(
            db,
            model_class=ErpWebhookEvent,
            tenant_id=tenant_id,
            record_data={
                "connector_type": normalised_connector,
                "message_id": message_id,
                "event_type": raw_event_type,
                "canonical_event_type": canonical_event_type,
                "received_at": _utcnow().isoformat(),
            },
            values={
                "id": uuid.uuid4(),
                "connector_type": normalised_connector,
                "message_id": message_id,
                "event_type": raw_event_type,
                "canonical_event_type": canonical_event_type,
                "payload": payload,
                "raw_headers": {k: v for k, v in headers.items()},
                "signature_verified": signature_verified,
                "processed": False,
                "processed_at": None,
                "processing_error": None,
                "dead_lettered": False,
                "dead_letter_reason": None,
                "received_at": _utcnow(),
            },
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        duplicate_after_race = (await db.execute(duplicate_stmt)).scalar_one_or_none()
        if duplicate_after_race is not None:
            return duplicate_after_race
        raise

    _enqueue_webhook_processing(
        event_id=str(event.id),
        tenant_id=str(tenant_id),
        canonical_event_type=canonical_event_type,
    )
    logger.info(
        "ERP webhook ingested and queued",
        extra={
            "tenant_id": str(tenant_id),
            "event_id": str(event.id),
            "connector_type": normalised_connector,
            "message_id": message_id,
            "canonical_event_type": canonical_event_type,
        },
    )
    return event


def _enqueue_webhook_processing(
    *,
    event_id: str,
    tenant_id: str,
    canonical_event_type: str,
) -> None:
    from financeops.modules.erp_push.application.webhook_task import process_webhook_event_task

    process_webhook_event_task.apply_async(
        kwargs={
            "event_id": event_id,
            "tenant_id": tenant_id,
            "canonical_event_type": canonical_event_type,
        },
        queue="normal_q",
    )
