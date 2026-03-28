from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.erp_sync import ErpAccountExternalRef
from financeops.db.models.erp_webhook import (
    CanonicalWebhookEventType,
    ErpWebhookEvent,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


async def process_webhook_event(
    db: AsyncSession,
    *,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID,
    canonical_event_type: str,
) -> dict[str, Any]:
    stmt = select(ErpWebhookEvent).where(
        ErpWebhookEvent.id == event_id,
        ErpWebhookEvent.tenant_id == tenant_id,
    )
    event = (await db.execute(stmt)).scalar_one_or_none()

    if event is None:
        return {"outcome": "NOT_FOUND", "event_id": str(event_id)}

    if event.processed:
        return {"outcome": "ALREADY_PROCESSED", "event_id": str(event_id)}

    outcome = await _dispatch(
        db=db,
        event=event,
        tenant_id=tenant_id,
        canonical_event_type=canonical_event_type,
    )

    if outcome["status"] == "DEAD_LETTERED":
        event.dead_lettered = True
        event.dead_letter_reason = str(outcome.get("reason") or "Unknown event type")
    else:
        event.processed = True
        event.processed_at = _utcnow()
        if outcome["status"] == "ERROR":
            event.processing_error = str(outcome.get("error") or "")

    await db.flush()
    await db.commit()

    return {"outcome": outcome["status"], "event_id": str(event_id)}


async def _dispatch(
    *,
    db: AsyncSession,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
    canonical_event_type: str,
) -> dict[str, str]:
    try:
        if canonical_event_type == CanonicalWebhookEventType.PAYMENT_RECEIVED:
            return await _handle_payment_received(event=event, tenant_id=tenant_id)

        if canonical_event_type in {
            CanonicalWebhookEventType.INVOICE_UPDATED,
            CanonicalWebhookEventType.INVOICE_CREATED,
        }:
            return await _handle_invoice_event(event=event, tenant_id=tenant_id)

        if canonical_event_type in {
            CanonicalWebhookEventType.ACCOUNT_CREATED,
            CanonicalWebhookEventType.ACCOUNT_UPDATED,
        }:
            return await _handle_account_event(db=db, event=event, tenant_id=tenant_id)

        if canonical_event_type in {
            CanonicalWebhookEventType.VENDOR_CREATED,
            CanonicalWebhookEventType.VENDOR_UPDATED,
        }:
            return await _handle_vendor_event(event=event, tenant_id=tenant_id)

        if canonical_event_type in {
            CanonicalWebhookEventType.JOURNAL_CREATED,
            CanonicalWebhookEventType.JOURNAL_UPDATED,
        }:
            return await _handle_journal_event(event=event, tenant_id=tenant_id)

        return await _handle_unknown(event=event, tenant_id=tenant_id)
    except Exception as exc:  # pragma: no cover - defensive async worker path
        logger.exception(
            "ERP webhook processing error",
            extra={
                "event_id": str(event.id),
                "tenant_id": str(tenant_id),
                "canonical_event_type": canonical_event_type,
            },
        )
        return {"status": "ERROR", "error": str(exc)}


async def _handle_payment_received(
    *,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    logger.info(
        "ERP webhook payment_received",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "event_id": str(event.id),
        },
    )
    return {"status": "PROCESSED", "action": "payment_logged"}


async def _handle_invoice_event(
    *,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    logger.info(
        "ERP webhook invoice event",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "event_type": event.event_type,
            "event_id": str(event.id),
        },
    )
    return {"status": "PROCESSED", "action": "invoice_flagged_for_review"}


async def _handle_account_event(
    *,
    db: AsyncSession,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    payload = event.payload or {}
    external_account_id = str(payload.get("account_id") or payload.get("Id") or "").strip()
    if external_account_id:
        stmt = (
            update(ErpAccountExternalRef)
            .where(
                ErpAccountExternalRef.tenant_id == tenant_id,
                ErpAccountExternalRef.connector_type == event.connector_type,
                ErpAccountExternalRef.external_account_id == external_account_id,
            )
            .values(
                is_stale=True,
                stale_detected_at=_utcnow(),
            )
        )
        await db.execute(stmt)

    logger.info(
        "ERP webhook account event",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "external_account_id": external_account_id,
            "event_id": str(event.id),
        },
    )
    return {"status": "PROCESSED", "action": "account_marked_stale"}


async def _handle_vendor_event(
    *,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    logger.info(
        "ERP webhook vendor event",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "event_id": str(event.id),
        },
    )
    return {"status": "PROCESSED", "action": "vendor_change_logged"}


async def _handle_journal_event(
    *,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    logger.info(
        "ERP webhook journal event",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "event_id": str(event.id),
        },
    )
    return {"status": "PROCESSED", "action": "journal_logged"}


async def _handle_unknown(
    *,
    event: ErpWebhookEvent,
    tenant_id: uuid.UUID,
) -> dict[str, str]:
    logger.warning(
        "ERP webhook unknown event dead-lettered",
        extra={
            "tenant_id": str(tenant_id),
            "connector_type": event.connector_type,
            "event_type": event.event_type,
            "event_id": str(event.id),
        },
    )
    return {
        "status": "DEAD_LETTERED",
        "reason": f"Unrecognised event type: {event.event_type}",
    }
