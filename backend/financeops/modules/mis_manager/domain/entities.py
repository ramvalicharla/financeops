from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from financeops.modules.mis_manager.domain.enums import DriftType, ValidationStatus
from financeops.modules.mis_manager.domain.value_objects import SignatureBundle


@dataclass(frozen=True)
class SheetProfile:
    sheet_name: str
    header_row_index: int
    data_start_row_index: int
    headers: list[str]
    row_labels: list[str]
    column_order: list[str]
    section_breaks: list[str]
    blank_row_density: Decimal
    formula_density: Decimal
    text_to_numeric_ratio: Decimal
    merged_cell_count: int


@dataclass(frozen=True)
class TemplateDetectionResult:
    signature: SignatureBundle
    detection_summary: dict[str, Any]
    template_match_outcome: str
    prior_template_version_id: UUID | None


@dataclass(frozen=True)
class DriftAssessment:
    drift_type: DriftType
    is_material: bool
    details: dict[str, Any]


@dataclass(frozen=True)
class CanonicalMapping:
    source_label: str
    normalized_label: str
    canonical_metric_code: str | None
    canonical_dimension_code: str | None
    confidence_score: Decimal


@dataclass(frozen=True)
class NormalizedLine:
    line_no: int
    canonical_metric_code: str
    canonical_dimension_json: dict[str, Any]
    source_row_ref: str
    source_column_ref: str
    period_value: Decimal
    currency_code: str
    sign_applied: str
    validation_status: ValidationStatus


@dataclass(frozen=True)
class ValidationException:
    exception_code: str
    severity: str
    source_ref: str
    message: str


@dataclass(frozen=True)
class SnapshotBuildResult:
    snapshot_token: str
    normalized_lines: list[NormalizedLine] = field(default_factory=list)
    exceptions: list[ValidationException] = field(default_factory=list)
    validation_summary_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotContext:
    tenant_id: UUID
    organisation_id: UUID
    template_id: UUID
    template_version_id: UUID
    reporting_period: date
    upload_artifact_id: UUID
    source_file_hash: str
    sheet_name: str
    created_by: UUID
    status: str
