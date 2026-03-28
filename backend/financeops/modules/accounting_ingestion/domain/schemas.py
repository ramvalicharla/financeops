from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    tax_amount: Decimal | None = None
    hsn_sac_code: str | None = None


class NormalisedExtractionResult(BaseModel):
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    vendor_pan: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total: Decimal | None = None
    currency: str = "INR"
    billed_to_name: str | None = None
    billed_to_gstin: str | None = None
    confidence_per_field: dict[str, float] = Field(default_factory=dict)
    low_quality: bool = False
    low_quality_reason: str | None = None
    multi_invoice_detected: bool = False
    requires_manual_review: bool = False
    raw_response: dict[str, Any] | None = None


class EntityDetectionSignal(BaseModel):
    signal_type: str
    entity_id: uuid.UUID
    confidence: float
    reason: str


class EntityDetectionResult(BaseModel):
    detected_entity_id: uuid.UUID | None = None
    confidence: float = 0.0
    signals: list[EntityDetectionSignal] = Field(default_factory=list)
    requires_manual_queue: bool = False
    reason: str | None = None


class IngestionResult(BaseModel):
    success: bool
    email_message_id: uuid.UUID | None = None
    portal_submission_id: uuid.UUID | None = None
    attachment_id: uuid.UUID | None = None
    extraction: NormalisedExtractionResult | None = None
    entity_detection: EntityDetectionResult | None = None
    jv_draft_id: uuid.UUID | None = None
    error: str | None = None
