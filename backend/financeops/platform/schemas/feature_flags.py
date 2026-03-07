from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FeatureFlagCreate(BaseModel):
    module_id: uuid.UUID
    flag_key: str = Field(min_length=1, max_length=128)
    flag_value: dict[str, Any] = Field(default_factory=dict)
    rollout_mode: str = Field(pattern="^(off|on|canary)$")
    compute_enabled: bool
    write_enabled: bool
    visibility_enabled: bool
    target_scope_type: str = Field(pattern="^(tenant|user|entity|canary)$")
    target_scope_id: uuid.UUID | None = None
    traffic_percent: float | None = Field(default=None, ge=0, le=100)
    effective_from: datetime
    effective_to: datetime | None = None


class FeatureFlagEvaluationResult(BaseModel):
    enabled: bool
    compute_enabled: bool
    write_enabled: bool
    visibility_enabled: bool
    selected_flag_id: str | None
    rollout_mode: str


class FeatureFlagEvaluationRequest(BaseModel):
    module_id: uuid.UUID
    flag_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(default="default", min_length=1, max_length=128)
    user_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
