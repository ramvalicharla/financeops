from __future__ import annotations

import abc
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_vendor import AccountingVendor
from financeops.modules.accounting_ingestion.domain.schemas import (
    EntityDetectionResult,
    EntityDetectionSignal,
    ExtractedLineItem,
    NormalisedExtractionResult,
)
from financeops.platform.db.models.entities import CpEntity
from financeops.services.network_runtime import create_textract_client
from financeops.utils.gstin import validate_gstin

logger = logging.getLogger(__name__)

_MIN_FIELD_CONFIDENCE = 0.70
_MIN_ENTITY_CONFIDENCE = 0.60


class DocumentExtractor(abc.ABC):
    @abc.abstractmethod
    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> NormalisedExtractionResult:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError


class TextractProvider(DocumentExtractor):
    provider_name = "TEXTRACT"

    def __init__(self, region: str = "ap-south-1") -> None:
        self._region = region

    def _get_client(self) -> Any:
        return create_textract_client(self._region)

    def _to_decimal(self, value: str | None) -> Decimal | None:
        if not value:
            return None
        cleaned = value.replace(",", "").replace("\u20b9", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    def _parse_date(self, value: str | None) -> date | None:
        if not value:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _extract_field(
        self,
        expense_fields: list[dict[str, Any]],
        field_type: str,
    ) -> tuple[str | None, float]:
        for field in expense_fields:
            parsed_type = str(field.get("Type", {}).get("Text", "")).upper()
            if parsed_type == field_type.upper():
                value = field.get("ValueDetection", {}).get("Text")
                confidence_raw = field.get("ValueDetection", {}).get("Confidence", 0.0)
                confidence = float(confidence_raw) / 100.0
                return value, confidence
        return None, 0.0

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> NormalisedExtractionResult:
        _ = mime_type
        client = self._get_client()

        try:
            response = client.analyze_expense(Document={"Bytes": file_bytes})
        except Exception as exc:  # pragma: no cover - network/provider path
            logger.error("Textract extraction failed: %s", exc)
            return NormalisedExtractionResult(
                low_quality=True,
                low_quality_reason=f"Textract error: {exc}",
                requires_manual_review=True,
                raw_response={"error": str(exc), "filename": filename},
            )

        expense_docs = response.get("ExpenseDocuments", [])
        if not expense_docs:
            return NormalisedExtractionResult(
                low_quality=True,
                low_quality_reason="No expense documents detected",
                requires_manual_review=True,
                raw_response=response,
            )

        multi_invoice = len(expense_docs) > 1
        doc = expense_docs[0]
        summary_fields = doc.get("SummaryFields", [])
        line_item_groups = doc.get("LineItemGroups", [])
        confidence_map: dict[str, float] = {}

        vendor_name, confidence_map["vendor_name"] = self._extract_field(summary_fields, "VENDOR_NAME")
        invoice_number, confidence_map["invoice_number"] = self._extract_field(
            summary_fields, "INVOICE_RECEIPT_ID"
        )
        invoice_date_raw, confidence_map["invoice_date"] = self._extract_field(
            summary_fields, "INVOICE_RECEIPT_DATE"
        )
        due_date_raw, confidence_map["due_date"] = self._extract_field(summary_fields, "DUE_DATE")
        total_raw, confidence_map["total"] = self._extract_field(summary_fields, "AMOUNT_DUE")
        if not total_raw:
            total_raw, confidence_map["total"] = self._extract_field(summary_fields, "TOTAL")
        tax_raw, confidence_map["tax_amount"] = self._extract_field(summary_fields, "TAX")
        subtotal_raw, confidence_map["subtotal"] = self._extract_field(summary_fields, "SUBTOTAL")
        gstin_raw, confidence_map["vendor_gstin"] = self._extract_field(summary_fields, "TAX_PAYER_ID")
        billed_to_name, confidence_map["billed_to_name"] = self._extract_field(summary_fields, "RECEIVER_NAME")

        line_items: list[ExtractedLineItem] = []
        for group in line_item_groups:
            for item in group.get("LineItems", []):
                fields = item.get("LineItemExpenseFields", [])
                description, _ = self._extract_field(fields, "ITEM")
                quantity_raw, _ = self._extract_field(fields, "QUANTITY")
                unit_price_raw, _ = self._extract_field(fields, "UNIT_PRICE")
                amount_raw, _ = self._extract_field(fields, "EXPENSE_ROW")
                line_items.append(
                    ExtractedLineItem(
                        description=description,
                        quantity=self._to_decimal(quantity_raw),
                        unit_price=self._to_decimal(unit_price_raw),
                        amount=self._to_decimal(amount_raw),
                    )
                )

        vendor_gstin = None
        if gstin_raw:
            candidate = gstin_raw.strip().upper()
            if validate_gstin(candidate):
                vendor_gstin = candidate

        key_confidence = [
            confidence_map.get("vendor_name", 0.0),
            confidence_map.get("invoice_number", 0.0),
            confidence_map.get("total", 0.0),
        ]
        avg_confidence = sum(key_confidence) / len(key_confidence)
        low_quality = avg_confidence < _MIN_FIELD_CONFIDENCE

        return NormalisedExtractionResult(
            vendor_name=vendor_name,
            vendor_gstin=vendor_gstin,
            invoice_number=invoice_number,
            invoice_date=self._parse_date(invoice_date_raw),
            due_date=self._parse_date(due_date_raw),
            line_items=line_items,
            subtotal=self._to_decimal(subtotal_raw),
            tax_amount=self._to_decimal(tax_raw),
            total=self._to_decimal(total_raw),
            currency="INR",
            billed_to_name=billed_to_name,
            confidence_per_field=confidence_map,
            low_quality=low_quality,
            low_quality_reason=(
                f"Average key field confidence {avg_confidence:.2f} below threshold {_MIN_FIELD_CONFIDENCE}"
                if low_quality
                else None
            ),
            multi_invoice_detected=multi_invoice,
            requires_manual_review=low_quality or multi_invoice,
            raw_response={"expense_document_count": len(expense_docs)},
        )


async def detect_entity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    extraction: NormalisedExtractionResult,
    routing_entity_id: uuid.UUID | None = None,
    user_session_entity_id: uuid.UUID | None = None,
) -> EntityDetectionResult:
    signals: list[EntityDetectionSignal] = []

    if routing_entity_id is not None:
        signals.append(
            EntityDetectionSignal(
                signal_type="ROUTING_RULE",
                entity_id=routing_entity_id,
                confidence=1.0,
                reason="Email or folder routing rule matched",
            )
        )

    if extraction.billed_to_gstin and validate_gstin(extraction.billed_to_gstin):
        entity = await _match_gstin_to_entity(db, tenant_id=tenant_id, gstin=extraction.billed_to_gstin)
        if entity is not None:
            signals.append(
                EntityDetectionSignal(
                    signal_type="GSTIN_MATCH",
                    entity_id=entity,
                    confidence=0.95,
                    reason=f"GSTIN {extraction.billed_to_gstin} matched entity",
                )
            )

    if extraction.billed_to_name:
        entity = await _fuzzy_match_entity_name(
            db,
            tenant_id=tenant_id,
            name=extraction.billed_to_name,
        )
        if entity is not None:
            signals.append(
                EntityDetectionSignal(
                    signal_type="NAME_FUZZY_MATCH",
                    entity_id=entity,
                    confidence=0.70,
                    reason=f"Name '{extraction.billed_to_name}' fuzzy matched entity",
                )
            )

    if extraction.vendor_gstin:
        entity = await _match_vendor_gstin_to_entity(
            db,
            tenant_id=tenant_id,
            vendor_gstin=extraction.vendor_gstin,
        )
        if entity is not None:
            signals.append(
                EntityDetectionSignal(
                    signal_type="VENDOR_MASTER",
                    entity_id=entity,
                    confidence=0.65,
                    reason=f"Vendor GSTIN {extraction.vendor_gstin} matched vendor master",
                )
            )

    if user_session_entity_id is not None:
        signals.append(
            EntityDetectionSignal(
                signal_type="USER_SESSION",
                entity_id=user_session_entity_id,
                confidence=0.40,
                reason="User session context signal",
            )
        )

    if not signals:
        return EntityDetectionResult(
            detected_entity_id=None,
            confidence=0.0,
            signals=[],
            requires_manual_queue=True,
            reason="No entity signals detected",
        )

    best_signal = max(signals, key=lambda s: s.confidence)
    requires_manual = best_signal.confidence < _MIN_ENTITY_CONFIDENCE
    return EntityDetectionResult(
        detected_entity_id=best_signal.entity_id,
        confidence=best_signal.confidence,
        signals=signals,
        requires_manual_queue=requires_manual,
        reason=f"Best signal: {best_signal.signal_type} ({best_signal.confidence:.2f})",
    )


async def _match_gstin_to_entity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    gstin: str,
) -> uuid.UUID | None:
    stmt = (
        select(CpEntity)
        .where(
            CpEntity.tenant_id == tenant_id,
            CpEntity.gstin == gstin.upper(),
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row.id if row is not None else None


async def _fuzzy_match_entity_name(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
) -> uuid.UUID | None:
    trimmed = name.strip().lower()
    if not trimmed:
        return None
    stmt = (
        select(CpEntity)
        .where(
            CpEntity.tenant_id == tenant_id,
            sqlfunc.lower(CpEntity.entity_name).contains(trimmed[:50]),
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row.id if row is not None else None


async def _match_vendor_gstin_to_entity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    vendor_gstin: str,
) -> uuid.UUID | None:
    stmt = (
        select(AccountingVendor)
        .where(
            AccountingVendor.tenant_id == tenant_id,
            AccountingVendor.gstin == vendor_gstin.upper(),
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row.entity_id if row is not None else None
