from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class SourceDetectRequest(BaseModel):
    source_code: str
    file_name: str
    file_content_base64: str
    source_family_hint: str | None = None
    sheet_name: str | None = None


class SourceCommitVersionRequest(BaseModel):
    organisation_id: uuid.UUID
    source_family: str
    source_code: str
    source_name: str
    structure_hash: str
    header_hash: str
    row_signature_hash: str
    source_detection_summary_json: dict[str, Any]
    activate: bool = True


class RunUploadRequest(BaseModel):
    organisation_id: uuid.UUID
    source_id: uuid.UUID
    source_version_id: uuid.UUID
    run_type: str
    reporting_period: date
    source_artifact_id: uuid.UUID
    file_name: str
    file_content_base64: str
    sheet_name: str | None = None


class RunActionResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    run_status: str
    idempotent: bool


class RunUploadResponse(RunActionResponse):
    intent_id: uuid.UUID
    job_id: uuid.UUID
    payroll_line_count: int = 0
    gl_line_count: int = 0
    exception_count: int = 0
    source_airlock_item_id: uuid.UUID | None = None


class SourceSummaryResponse(BaseModel):
    id: uuid.UUID
    source_family: str
    source_code: str
    source_name: str
    status: str
    created_at: str


class SourceVersionSummaryResponse(BaseModel):
    id: uuid.UUID
    version_no: int
    version_token: str
    status: str
    structure_hash: str
    created_at: str


class RunSummaryResponse(BaseModel):
    payroll_line_count: int
    gl_line_count: int
    exception_count: int
