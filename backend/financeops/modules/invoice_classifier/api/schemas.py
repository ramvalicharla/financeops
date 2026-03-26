from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceClassifyRequest(BaseModel):
    entity_id: uuid.UUID
    invoice_number: str
    vendor_name: str
    invoice_date: date | None = None
    invoice_amount: Decimal
    line_description: str


class InvoiceReviewRequest(BaseModel):
    confirmed_classification: str
    notes: str | None = None


class InvoiceRouteResponse(BaseModel):
    routed_record_id: uuid.UUID
    routing_action: str


class InvoiceClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    invoice_number: str
    vendor_name: str | None = None
    invoice_date: date | None = None
    invoice_amount: Decimal
    line_description: str | None = None
    classification: str
    confidence: Decimal
    classification_method: str
    rule_matched: str | None = None
    ai_reasoning: str | None = None
    requires_human_review: bool
    human_reviewed_by: uuid.UUID | None = None
    human_reviewed_at: datetime | None = None
    human_override: str | None = None
    routing_action: str | None = None
    routed_record_id: uuid.UUID | None = None
    created_at: datetime


class ClassificationRuleCreateRequest(BaseModel):
    rule_name: str
    description: str | None = None
    pattern_type: str
    pattern_value: str
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    classification: str
    confidence: Decimal
    priority: int = 100
    is_active: bool = True


class ClassificationRuleUpdateRequest(BaseModel):
    rule_name: str | None = None
    description: str | None = None
    pattern_type: str | None = None
    pattern_value: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    classification: str | None = None
    confidence: Decimal | None = None
    priority: int | None = None
    is_active: bool | None = None


class ClassificationRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    rule_name: str
    description: str | None = None
    pattern_type: str
    pattern_value: str
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    classification: str
    confidence: Decimal
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class QueueQueryParams(BaseModel):
    entity_id: uuid.UUID
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


__all__ = [
    "InvoiceClassifyRequest",
    "InvoiceReviewRequest",
    "InvoiceRouteResponse",
    "InvoiceClassificationResponse",
    "ClassificationRuleCreateRequest",
    "ClassificationRuleUpdateRequest",
    "ClassificationRuleResponse",
]
