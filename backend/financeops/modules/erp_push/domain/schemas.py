from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PushJournalLine(BaseModel):
    account_code: str
    external_account_id: str
    entry_type: str
    amount: Decimal
    currency: str = "INR"
    narration: str | None = None
    tax_code: str | None = None


class PushJournalPacket(BaseModel):
    jv_id: uuid.UUID
    jv_number: str
    jv_version: int
    period_date: str
    description: str | None
    reference: str | None
    currency: str
    lines: list[PushJournalLine]
    entity_id: uuid.UUID
    connector_type: str
    idempotency_key: str = Field(default="")


class PushResult(BaseModel):
    success: bool
    external_journal_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    raw_response: dict[str, Any] | None = None


class AttachmentPushResult(BaseModel):
    success: bool
    external_document_id: str | None = None
    error_message: str | None = None
