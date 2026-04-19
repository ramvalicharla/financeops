from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import Task
from sqlalchemy import select

from financeops.db.models.accounting_vendor import AccountingAttachment
from financeops.db.session import tenant_session
from financeops.modules.accounting_ingestion.application.ocr_pipeline_service import (
    TextractProvider,
    detect_entity,
)
from financeops.storage.provider import get_storage
from financeops.tasks.async_runner import run_async
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    max_retries=3,
    queue="normal_q",
    name="accounting_ingestion.run_ocr_pipeline",
)
def run_ocr_pipeline_task(
    self: Task,
    attachment_id: str | None,
    tenant_id: str,
    entity_id: str | None,
    source_type: str,
    source_id: str,
    r2_key: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with tenant_session(tenant_id) as db:
            file_bytes, resolved_filename, mime_type = await _download_from_r2(
                db=db,
                attachment_id=attachment_id,
                r2_key=r2_key,
                filename=filename,
            )
            if not file_bytes:
                return {"outcome": "NO_FILE", "source_type": source_type, "source_id": source_id}

            provider = TextractProvider()
            extraction = await provider.extract(
                file_bytes=file_bytes,
                filename=resolved_filename,
                mime_type=mime_type,
            )
            entity_detection = await detect_entity(
                db,
                tenant_id=uuid.UUID(tenant_id),
                extraction=extraction,
                routing_entity_id=uuid.UUID(entity_id) if entity_id else None,
            )
            return {
                "outcome": "COMPLETED",
                "source_type": source_type,
                "source_id": source_id,
                "requires_manual_review": extraction.requires_manual_review,
                "detected_entity_id": (
                    str(entity_detection.detected_entity_id)
                    if entity_detection.detected_entity_id
                    else None
                ),
                "confidence": entity_detection.confidence,
            }

    try:
        return run_async(_run())
    except Exception as exc:  # pragma: no cover - celery retry behavior
        logger.exception(
            "OCR pipeline task failed",
            extra={"source_type": source_type, "source_id": source_id},
        )
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


async def _download_from_r2(
    *,
    db: Any,
    attachment_id: str | None,
    r2_key: str | None,
    filename: str | None,
) -> tuple[bytes, str, str]:
    storage = get_storage()

    if r2_key:
        try:
            data = storage.download_file(r2_key)
            return data, filename or "unknown", "application/octet-stream"
        except Exception:
            return b"", filename or "unknown", "application/octet-stream"

    if attachment_id:
        stmt = select(AccountingAttachment).where(AccountingAttachment.id == uuid.UUID(attachment_id))
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is not None and row.r2_key:
            try:
                data = storage.download_file(row.r2_key)
                return data, row.filename, row.mime_type
            except Exception:
                return b"", row.filename, row.mime_type

    return b"", "unknown", "application/octet-stream"
