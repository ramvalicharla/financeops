from __future__ import annotations

from enum import Enum


class ReconciliationStatus(str, Enum):
    MATCHED = "matched"
    EXCEPTION = "exception"
    REVIEW_REQUIRED = "review_required"


class DifferenceType(str, Enum):
    NONE = "none"
    MISSING_IN_A = "missing_in_a"
    MISSING_IN_B = "missing_in_b"
    VALUE_MISMATCH = "value_mismatch"
    MAPPING_GAP = "mapping_gap"
    TIMING_DIFFERENCE = "timing_difference"
    CLASSIFICATION_DIFFERENCE = "classification_difference"
    FX_DIFFERENCE = "fx_difference"
    AGGREGATION_DIFFERENCE = "aggregation_difference"


class ExceptionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ResolutionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    ACCEPTED = "accepted"


class ResolutionEventType(str, Enum):
    EXCEPTION_OPENED = "exception_opened"
    EXPLANATION_ADDED = "explanation_added"
    EVIDENCE_LINKED = "evidence_linked"
    ASSIGNED = "assigned"
    ACCEPTED_TIMING_DIFFERENCE = "accepted_timing_difference"
    ACCEPTED_MAPPING_GAP = "accepted_mapping_gap"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    REOPENED = "reopened"
