from __future__ import annotations

from enum import StrEnum


class TemplateType(StrEnum):
    PNL_MONTHLY = "pnl_monthly"
    BALANCE_SHEET_MONTHLY = "balance_sheet_monthly"
    CASHFLOW_MONTHLY = "cashflow_monthly"
    DEPARTMENT_MIS = "department_mis"
    PROJECT_MIS = "project_mis"
    CUSTOM = "custom"


class TemplateVersionStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class SnapshotStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FINALIZED = "finalized"
    FAILED = "failed"


class ColumnRole(StrEnum):
    PERIOD = "period"
    METRIC_NAME = "metric_name"
    VALUE = "value"
    DIMENSION = "dimension"
    SUBTOTAL_FLAG = "subtotal_flag"
    FORMULA_FLAG = "formula_flag"
    NOTES = "notes"


class DriftType(StrEnum):
    HEADER_CHANGE = "HEADER_CHANGE"
    SECTION_REORDER = "SECTION_REORDER"
    PERIOD_AXIS_CHANGE = "PERIOD_AXIS_CHANGE"
    DIMENSION_CHANGE = "DIMENSION_CHANGE"
    ROW_PATTERN_CHANGE = "ROW_PATTERN_CHANGE"
    MAJOR_LAYOUT_CHANGE = "MAJOR_LAYOUT_CHANGE"


class DriftDecisionStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ValidationStatus(StrEnum):
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class ExceptionSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExceptionResolutionStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
