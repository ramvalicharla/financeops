from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.db.models.accounting_ingestion import (
    AccountingInboundEmailMessage,
    EmailProcessingStatus,
)
from financeops.modules.accounting_ingestion.application.airlock_actor import (
    resolve_airlock_actor,
)
from financeops.services.audit_writer import AuditWriter
from financeops.storage.provider import get_storage

logger = logging.getLogger(__name__)


def _is_sender_whitelisted(sender_email: str, whitelist: list[str]) -> bool:
    sender = sender_email.lower().strip()
    for entry in whitelist:
        item = entry.lower().strip()
        if item.startswith("@") and sender.endswith(item):
            return True
        if sender == item:
            return True
    return False


async def ingest_email(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    message_id: str,
    sender_email: str,
    sender_name: str | None,
    subject: str | None,
    attachment_bytes_list: list[tuple[str, bytes, str]],
    raw_metadata: dict[str, Any] | None = None,
    sender_whitelist: list[str] | None = None,
    entity_routing_id: uuid.UUID | None = None,
) -> AccountingInboundEmailMessage:
    sender_whitelist = sender_whitelist or []
    normalized_message_id = message_id.strip()
    normalized_sender = sender_email.lower().strip()

    dup_stmt = select(AccountingInboundEmailMessage).where(
        AccountingInboundEmailMessage.tenant_id == tenant_id,
        AccountingInboundEmailMessage.message_id == normalized_message_id,
    )
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    whitelisted = _is_sender_whitelisted(normalized_sender, sender_whitelist)
    status = EmailProcessingStatus.PENDING if whitelisted else EmailProcessingStatus.REJECTED
    try:
        msg = await AuditWriter.insert_financial_record(
            db,
            model_class=AccountingInboundEmailMessage,
            tenant_id=tenant_id,
            record_data={
                "message_id": normalized_message_id,
                "sender_email": normalized_sender,
                "entity_id": str(entity_routing_id) if entity_routing_id else None,
                "status": status,
            },
            values={
                "id": uuid.uuid4(),
                "entity_id": entity_routing_id,
                "message_id": normalized_message_id,
                "sender_email": normalized_sender,
                "sender_name": sender_name,
                "subject": subject,
                "sender_whitelisted": whitelisted,
                "processing_status": status,
                "attachment_count": len(attachment_bytes_list),
                "auto_reply_sent": False,
                "raw_metadata": raw_metadata,
            },
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raced = (await db.execute(dup_stmt)).scalar_one_or_none()
        if raced is not None:
            return raced
        raise

    if not whitelisted:
        return msg

    processed = 0
    airlock_actor = await resolve_airlock_actor(db, tenant_id=tenant_id)
    for filename, file_bytes, mime_type in attachment_bytes_list:
        ok = await _process_attachment(
            db=db,
            tenant_id=tenant_id,
            filename=filename,
            file_bytes=file_bytes,
            mime_type=mime_type,
            entity_id=entity_routing_id,
            email_message_id=msg.id,
            airlock_actor=airlock_actor,
        )
        if ok:
            processed += 1
    logger.info(
        "Inbound email ingested: tenant=%s message_id=%s processed_attachments=%d",
        str(tenant_id)[:8],
        normalized_message_id,
        processed,
    )
    return msg


async def _process_attachment(
    *,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
    entity_id: uuid.UUID | None,
    email_message_id: uuid.UUID,
    airlock_actor,
) -> bool:
    airlock_service = AirlockAdmissionService()
    try:
        submitted = await airlock_service.submit_external_input(
            db,
            source_type="inbound_email_attachment",
            actor=airlock_actor,
            metadata={"email_message_id": str(email_message_id)},
            content=file_bytes,
            file_name=filename,
            entity_id=entity_id,
            source_reference=str(email_message_id),
            idempotency_key=f"{tenant_id}:{email_message_id}:{filename}",
        )
        await airlock_service.admit_airlock_item(
            db,
            item_id=submitted.item_id,
            actor=airlock_actor,
        )
        airlock_item = await airlock_service.get_item(db, tenant_id=tenant_id, item_id=submitted.item_id)
    except ValidationError as exc:
        logger.warning(
            "Inbound email attachment rejected: tenant=%s file=%s reason=%s",
            str(tenant_id)[:8],
            filename,
            exc,
        )
        return False

    storage = get_storage()
    r2_key = f"ingestion/{tenant_id}/{airlock_item.checksum_sha256}/{filename}"
    try:
        storage.upload_file(
            file_bytes,
            key=r2_key,
            content_type=airlock_item.mime_type or mime_type,
            tenant_id=str(tenant_id),
            uploaded_by=None,
        )
    except Exception as exc:
        logger.warning("r2_upload_failed location=email_ingestion error=%s", exc)
        raise

    _enqueue_ocr(
        tenant_id=str(tenant_id),
        entity_id=str(entity_id) if entity_id is not None else None,
        source_type="EMAIL",
        source_id=str(email_message_id),
        r2_key=r2_key,
        filename=filename,
    )
    return True


def _enqueue_ocr(
    *,
    tenant_id: str,
    entity_id: str | None,
    source_type: str,
    source_id: str,
    r2_key: str,
    filename: str,
) -> None:
    from financeops.modules.accounting_ingestion.application.ocr_task import (
        run_ocr_pipeline_task,
    )

    run_ocr_pipeline_task.apply_async(
        kwargs={
            "attachment_id": None,
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "source_type": source_type,
            "source_id": source_id,
            "r2_key": r2_key,
            "filename": filename,
        },
        queue="normal_q",
    )
