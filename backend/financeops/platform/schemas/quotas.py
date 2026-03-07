from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuotaAssignmentCreate(BaseModel):
    quota_type: str = Field(min_length=1, max_length=64)
    window_type: str = Field(pattern="^(tumbling|sliding)$")
    window_seconds: int = Field(ge=1)
    max_value: int = Field(ge=1)
    enforcement_mode: str = Field(pattern="^(reject|queue|throttle)$")
    effective_from: datetime
    effective_to: datetime | None = None


class QuotaCheckRequest(BaseModel):
    quota_type: str
    usage_delta: int = Field(ge=1)
    operation_id: uuid.UUID | None = None
    idempotency_key: str
    request_fingerprint: str
    source_layer: str


class QuotaCheckResult(BaseModel):
    allowed: bool
    enforcement_mode: str
    code: str
    consumed_value: int
    max_value: int
    window_end: datetime
