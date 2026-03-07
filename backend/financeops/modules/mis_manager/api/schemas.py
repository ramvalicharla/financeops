from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateDetectRequest(BaseModel):
    organisation_id: UUID
    template_code: str = Field(min_length=1, max_length=128)
    template_name: str = Field(min_length=1, max_length=255)
    template_type: str = Field(min_length=1, max_length=64)
    file_name: str = Field(min_length=1, max_length=512)
    file_content_base64: str = Field(min_length=1)
    sheet_name: str | None = Field(default=None, max_length=255)


class TemplateCommitVersionRequest(BaseModel):
    organisation_id: UUID
    template_code: str = Field(min_length=1, max_length=128)
    template_name: str = Field(min_length=1, max_length=255)
    template_type: str = Field(min_length=1, max_length=64)
    structure_hash: str = Field(min_length=64, max_length=64)
    header_hash: str = Field(min_length=64, max_length=64)
    row_signature_hash: str = Field(min_length=64, max_length=64)
    column_signature_hash: str = Field(min_length=64, max_length=64)
    detection_summary_json: dict[str, Any]
    drift_reason: str | None = Field(default=None, max_length=512)
    activate: bool = False
    effective_from: date | None = None


class SnapshotUploadRequest(BaseModel):
    organisation_id: UUID
    template_id: UUID
    template_version_id: UUID
    reporting_period: date
    upload_artifact_id: UUID
    file_name: str = Field(min_length=1, max_length=512)
    file_content_base64: str = Field(min_length=1)
    sheet_name: str | None = Field(default=None, max_length=255)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)


class SnapshotStatusActionResponse(BaseModel):
    snapshot_id: UUID
    snapshot_status: str
    snapshot_token: str
    idempotent: bool


class SnapshotUploadResponse(SnapshotStatusActionResponse):
    line_count: int | None = None
    exception_count: int | None = None


class TemplateSummaryResponse(BaseModel):
    id: UUID
    template_code: str
    template_name: str
    template_type: str
    status: str
    created_at: str


class TemplateVersionSummaryResponse(BaseModel):
    id: UUID
    version_no: int
    version_token: str
    status: str
    structure_hash: str
    created_at: str
