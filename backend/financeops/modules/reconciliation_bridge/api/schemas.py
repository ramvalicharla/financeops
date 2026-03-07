from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationSessionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reconciliation_type: str
    source_a_type: str
    source_a_ref: str
    source_b_type: str
    source_b_ref: str
    period_start: date
    period_end: date
    matching_rule_version: str = "recon_match_v1"
    tolerance_rule_version: str = "recon_tolerance_v1"
    materiality_config_json: dict[str, Any] = Field(default_factory=dict)


class ReconciliationSessionCreateResponse(BaseModel):
    session_id: uuid.UUID
    session_token: str
    status: str
    idempotent: bool


class ReconciliationSessionRunResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    line_count: int
    exception_count: int
    idempotent: bool


class ReconciliationSessionSummaryResponse(BaseModel):
    line_count: int
    exception_line_count: int
    exception_count: int


class ReconciliationLineExplainRequest(BaseModel):
    explanation: str


class ReconciliationAttachEvidenceRequest(BaseModel):
    evidence_type: str
    evidence_ref: str
    evidence_label: str


class ReconciliationActionResponse(BaseModel):
    event_id: uuid.UUID | None = None
    exception_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
