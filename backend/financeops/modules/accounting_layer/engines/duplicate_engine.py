from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.accounting_vendor import (
    AccountingAttachment,
    AccountingDuplicateFingerprint,
    DuplicateAction,
)
from financeops.utils.gstin import validate_gstin

_DATE_TOLERANCE_DAYS = 3


def _amount_bucket(amount: Decimal) -> Decimal:
    if amount == Decimal("0"):
        return Decimal("0")
    magnitude = Decimal("10") ** max(amount.copy_abs().adjusted() - 2, -4)
    units = (amount / magnitude).to_integral_value(rounding=ROUND_FLOOR)
    return units * magnitude


def _date_bucket(invoice_date: date) -> date:
    epoch = date(2000, 1, 1)
    days_since = (invoice_date - epoch).days
    bucket_days = (days_since // _DATE_TOLERANCE_DAYS) * _DATE_TOLERANCE_DAYS
    return epoch + timedelta(days=bucket_days)


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def compute_layer2_fingerprint(
    invoice_number: str | None,
    vendor_gstin: str | None,
) -> str | None:
    if not invoice_number or not vendor_gstin:
        return None
    gstin = vendor_gstin.strip().upper()
    if not validate_gstin(gstin):
        return None
    normalized = f"{invoice_number.strip().upper()}:{gstin}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def compute_layer3_fingerprint(
    vendor_id: uuid.UUID | None,
    amount: Decimal | None,
    invoice_date: date | None,
) -> str | None:
    if not vendor_id or amount is None or invoice_date is None:
        return None
    amount_key = _amount_bucket(amount)
    date_key = _date_bucket(invoice_date)
    payload = f"{vendor_id}:{amount_key}:{date_key.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class DuplicateMatch:
    layer: int
    conflict_attachment_id: uuid.UUID
    conflict_jv_id: uuid.UUID | None
    fingerprint: str
    confidence: str


@dataclass
class DuplicateCheckResult:
    has_duplicates: bool
    matches: list[DuplicateMatch]
    flagged_fingerprint_ids: list[uuid.UUID]


async def check_for_duplicates(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    file_hash: str,
    invoice_number: str | None = None,
    vendor_gstin: str | None = None,
    vendor_id: uuid.UUID | None = None,
    amount: Decimal | None = None,
    invoice_date: date | None = None,
    jv_id: uuid.UUID | None = None,
) -> DuplicateCheckResult:
    matches: list[DuplicateMatch] = []
    fingerprint_ids: list[uuid.UUID] = []

    layer1_match = await _check_layer1(db, tenant_id, attachment_id, file_hash)
    if layer1_match is not None:
        matches.append(layer1_match)
        fingerprint_ids.append(
            await _log_fingerprint(
                db,
                tenant_id=tenant_id,
                attachment_id=attachment_id,
                jv_id=jv_id,
                layer=1,
                file_hash=file_hash,
                conflict_attachment_id=layer1_match.conflict_attachment_id,
                conflict_jv_id=layer1_match.conflict_jv_id,
            )
        )

    layer2_fingerprint = compute_layer2_fingerprint(invoice_number, vendor_gstin)
    if layer2_fingerprint is not None:
        layer2_match = await _check_layer2(db, tenant_id, attachment_id, layer2_fingerprint)
        if layer2_match is not None:
            matches.append(layer2_match)
            fingerprint_ids.append(
                await _log_fingerprint(
                    db,
                    tenant_id=tenant_id,
                    attachment_id=attachment_id,
                    jv_id=jv_id,
                    layer=2,
                    invoice_number=invoice_number,
                    vendor_gstin=vendor_gstin,
                    layer2_fingerprint=layer2_fingerprint,
                    conflict_attachment_id=layer2_match.conflict_attachment_id,
                    conflict_jv_id=layer2_match.conflict_jv_id,
                )
            )
    elif invoice_number and vendor_gstin:
        fingerprint_ids.append(
            await _log_fingerprint(
                db,
                tenant_id=tenant_id,
                attachment_id=attachment_id,
                jv_id=jv_id,
                layer=2,
                invoice_number=invoice_number,
                vendor_gstin=vendor_gstin,
                action=DuplicateAction.FLAGGED,
                action_reason="Invalid or dirty GSTIN - manual confirmation required",
            )
        )

    layer3_fingerprint = compute_layer3_fingerprint(vendor_id, amount, invoice_date)
    if layer3_fingerprint is not None:
        amount_bucket = _amount_bucket(amount) if amount is not None else None
        date_bucket = _date_bucket(invoice_date) if invoice_date is not None else None
        layer3_match = await _check_layer3(db, tenant_id, attachment_id, layer3_fingerprint)
        if layer3_match is not None:
            matches.append(layer3_match)
            fingerprint_ids.append(
                await _log_fingerprint(
                    db,
                    tenant_id=tenant_id,
                    attachment_id=attachment_id,
                    jv_id=jv_id,
                    layer=3,
                    vendor_id=vendor_id,
                    amount_bucket=amount_bucket,
                    date_bucket=date_bucket,
                    layer3_fingerprint=layer3_fingerprint,
                    conflict_attachment_id=layer3_match.conflict_attachment_id,
                    conflict_jv_id=layer3_match.conflict_jv_id,
                )
            )

    return DuplicateCheckResult(
        has_duplicates=bool(matches),
        matches=matches,
        flagged_fingerprint_ids=fingerprint_ids,
    )


async def record_override_action(
    db: AsyncSession,
    *,
    fingerprint_id: uuid.UUID,
    tenant_id: uuid.UUID,
    action: str,
    action_reason: str,
    action_by: uuid.UUID,
) -> AccountingDuplicateFingerprint:
    result = await db.execute(
        select(AccountingDuplicateFingerprint).where(
            AccountingDuplicateFingerprint.id == fingerprint_id,
            AccountingDuplicateFingerprint.tenant_id == tenant_id,
        )
    )
    original = result.scalar_one_or_none()
    if original is None:
        raise NotFoundError(f"Fingerprint {fingerprint_id} not found")

    if action not in (DuplicateAction.SKIPPED, DuplicateAction.OVERRIDDEN, DuplicateAction.RELATED):
        raise ValidationError(
            f"Invalid action '{action}'. Must be SKIPPED, OVERRIDDEN, or RELATED."
        )

    content = f"{original.attachment_id}:{action}:{action_by}"
    chain_hash = hashlib.sha256(content.encode()).hexdigest()

    override = AccountingDuplicateFingerprint(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=original.chain_hash,
        attachment_id=original.attachment_id,
        jv_id=original.jv_id,
        detection_layer=original.detection_layer,
        file_hash=original.file_hash,
        invoice_number=original.invoice_number,
        vendor_gstin=original.vendor_gstin,
        layer2_fingerprint=original.layer2_fingerprint,
        vendor_id=original.vendor_id,
        amount_bucket=original.amount_bucket,
        date_bucket=original.date_bucket,
        layer3_fingerprint=original.layer3_fingerprint,
        conflict_attachment_id=original.conflict_attachment_id,
        conflict_jv_id=original.conflict_jv_id,
        action=action,
        action_reason=action_reason,
        action_by=action_by,
    )
    db.add(override)
    await db.flush()
    return override


async def _check_layer1(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_attachment_id: uuid.UUID,
    file_hash: str,
) -> DuplicateMatch | None:
    result = await db.execute(
        select(AccountingAttachment)
        .where(
            AccountingAttachment.tenant_id == tenant_id,
            AccountingAttachment.sha256_hash == file_hash,
            AccountingAttachment.id != current_attachment_id,
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return None
    return DuplicateMatch(
        layer=1,
        conflict_attachment_id=existing.id,
        conflict_jv_id=existing.jv_id,
        fingerprint=file_hash,
        confidence="HIGH",
    )


async def _check_layer2(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_attachment_id: uuid.UUID,
    layer2_fingerprint: str,
) -> DuplicateMatch | None:
    result = await db.execute(
        select(AccountingDuplicateFingerprint)
        .where(
            AccountingDuplicateFingerprint.tenant_id == tenant_id,
            AccountingDuplicateFingerprint.layer2_fingerprint == layer2_fingerprint,
            AccountingDuplicateFingerprint.attachment_id != current_attachment_id,
            AccountingDuplicateFingerprint.action == DuplicateAction.FLAGGED,
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return None
    return DuplicateMatch(
        layer=2,
        conflict_attachment_id=existing.attachment_id,
        conflict_jv_id=existing.jv_id,
        fingerprint=layer2_fingerprint,
        confidence="HIGH",
    )


async def _check_layer3(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_attachment_id: uuid.UUID,
    layer3_fingerprint: str,
) -> DuplicateMatch | None:
    result = await db.execute(
        select(AccountingDuplicateFingerprint)
        .where(
            AccountingDuplicateFingerprint.tenant_id == tenant_id,
            AccountingDuplicateFingerprint.layer3_fingerprint == layer3_fingerprint,
            AccountingDuplicateFingerprint.attachment_id != current_attachment_id,
            AccountingDuplicateFingerprint.action == DuplicateAction.FLAGGED,
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return None
    return DuplicateMatch(
        layer=3,
        conflict_attachment_id=existing.attachment_id,
        conflict_jv_id=existing.jv_id,
        fingerprint=layer3_fingerprint,
        confidence="LOW",
    )


async def _log_fingerprint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    jv_id: uuid.UUID | None,
    layer: int,
    file_hash: str | None = None,
    invoice_number: str | None = None,
    vendor_gstin: str | None = None,
    layer2_fingerprint: str | None = None,
    vendor_id: uuid.UUID | None = None,
    amount_bucket: Decimal | None = None,
    date_bucket: date | None = None,
    layer3_fingerprint: str | None = None,
    conflict_attachment_id: uuid.UUID | None = None,
    conflict_jv_id: uuid.UUID | None = None,
    action: str = DuplicateAction.FLAGGED,
    action_reason: str | None = None,
) -> uuid.UUID:
    content = (
        f"{attachment_id}:{layer}:{file_hash or ''}:{layer2_fingerprint or ''}:"
        f"{layer3_fingerprint or ''}:{action}"
    )
    chain_hash = hashlib.sha256(content.encode()).hexdigest()

    fingerprint = AccountingDuplicateFingerprint(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash="",
        attachment_id=attachment_id,
        jv_id=jv_id,
        detection_layer=layer,
        file_hash=file_hash,
        invoice_number=invoice_number,
        vendor_gstin=vendor_gstin,
        layer2_fingerprint=layer2_fingerprint,
        vendor_id=vendor_id,
        amount_bucket=amount_bucket,
        date_bucket=date_bucket,
        layer3_fingerprint=layer3_fingerprint,
        conflict_attachment_id=conflict_attachment_id,
        conflict_jv_id=conflict_jv_id,
        action=action,
        action_reason=action_reason,
    )
    db.add(fingerprint)
    await db.flush()
    return fingerprint.id
