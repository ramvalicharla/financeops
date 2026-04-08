from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.governance.airlock import AirlockAdmissionService
from financeops.db.models.accounting_ingestion import (
    PortalSubmissionStatus,
    VendorPortalSubmission,
)
from financeops.db.models.accounting_vendor import AccountingVendor
from financeops.modules.accounting_ingestion.application.airlock_actor import (
    resolve_airlock_actor,
)
from financeops.services.audit_writer import AuditWriter
from financeops.storage.provider import get_storage

logger = logging.getLogger(__name__)


def _generate_reference_id() -> str:
    return secrets.token_urlsafe(12)[:16].upper()


async def _verify_vendor_email(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submitter_email: str,
) -> tuple[bool, uuid.UUID | None]:
    stmt = (
        select(AccountingVendor)
        .where(
            AccountingVendor.tenant_id == tenant_id,
            AccountingVendor.email == submitter_email.lower().strip(),
            AccountingVendor.is_active.is_(True),
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False, None
    return True, row.id


async def create_submission(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submitter_email: str,
    submitter_name: str | None,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    entity_id: uuid.UUID | None = None,
) -> VendorPortalSubmission:
    normalized_email = submitter_email.lower().strip()
    email_verified, vendor_id = await _verify_vendor_email(
        db,
        tenant_id=tenant_id,
        submitter_email=normalized_email,
    )
    airlock_service = AirlockAdmissionService()
    airlock_actor = await resolve_airlock_actor(db, tenant_id=tenant_id)
    accepted_by_airlock = False
    scan_status = "REJECTED"
    rejection_reason: str | None = None
    airlock_item = None
    try:
        submitted = await airlock_service.submit_external_input(
            db,
            source_type="vendor_portal_upload",
            actor=airlock_actor,
            metadata={"submitter_email": normalized_email, "vendor_id": str(vendor_id) if vendor_id else None},
            content=file_bytes,
            file_name=filename,
            entity_id=entity_id,
            source_reference=normalized_email,
            idempotency_key=f"{tenant_id}:{normalized_email}:{filename}",
        )
        await airlock_service.admit_airlock_item(db, item_id=submitted.item_id, actor=airlock_actor)
        airlock_item = await airlock_service.get_item(db, tenant_id=tenant_id, item_id=submitted.item_id)
        scan_status = airlock_item.status
        accepted_by_airlock = airlock_item.status == "ADMITTED"
    except ValidationError as exc:
        rejection_reason = str(exc)

    r2_key: str | None = None
    if accepted_by_airlock:
        assert airlock_item is not None
        r2_key = f"vendor_portal/{tenant_id}/{airlock_item.checksum_sha256}/{filename}"
        storage = get_storage()
        storage.upload_file(
            file_bytes,
            key=r2_key,
            content_type=airlock_item.mime_type or mime_type,
            tenant_id=str(tenant_id),
            uploaded_by=None,
        )

    reference_id = _generate_reference_id()
    public_status = (
        PortalSubmissionStatus.RECEIVED if accepted_by_airlock else PortalSubmissionStatus.REJECTED
    )

    submission = await AuditWriter.insert_financial_record(
        db,
        model_class=VendorPortalSubmission,
        tenant_id=tenant_id,
        record_data={
            "reference_id": reference_id,
            "submitter_email": normalized_email,
            "status": public_status,
            "scan_status": scan_status,
        },
        values={
            "id": uuid.uuid4(),
            "entity_id": entity_id,
            "vendor_id": vendor_id,
            "reference_id": reference_id,
            "submitter_email": normalized_email,
            "submitter_name": submitter_name,
            "vendor_email_verified": email_verified,
            "r2_key": r2_key,
            "filename": filename,
            "mime_type": (airlock_item.mime_type if airlock_item is not None else None) or mime_type,
            "file_size_bytes": airlock_item.size_bytes if airlock_item is not None else len(file_bytes),
            "sha256_hash": airlock_item.checksum_sha256 if airlock_item is not None else None,
            "scan_status": scan_status,
            "status": public_status,
            "rejection_reason": rejection_reason,
        },
    )
    await db.flush()

    if accepted_by_airlock and r2_key is not None:
        from financeops.modules.accounting_ingestion.application.ocr_task import (
            run_ocr_pipeline_task,
        )

        run_ocr_pipeline_task.apply_async(
            kwargs={
                "attachment_id": None,
                "tenant_id": str(tenant_id),
                "entity_id": str(entity_id) if entity_id else None,
                "source_type": "VENDOR_PORTAL",
                "source_id": str(submission.id),
                "r2_key": r2_key,
                "filename": filename,
            },
            queue="normal_q",
        )

    logger.info(
        "Vendor portal submission created: tenant=%s ref=%s status=%s",
        str(tenant_id)[:8],
        reference_id,
        submission.status,
    )
    return submission


async def get_submission_status(
    db: AsyncSession,
    *,
    reference_id: str,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    stmt = select(VendorPortalSubmission).where(
        VendorPortalSubmission.tenant_id == tenant_id,
        VendorPortalSubmission.reference_id == reference_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return {"found": False, "reference_id": reference_id}

    safe_status = row.status if row.status in PortalSubmissionStatus.ALL else PortalSubmissionStatus.UNDER_REVIEW
    return {
        "found": True,
        "reference_id": row.reference_id,
        "status": safe_status,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "filename": row.filename,
    }
