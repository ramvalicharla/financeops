from __future__ import annotations

from enum import Enum


class MappingStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RuleStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RuleType(str, Enum):
    AGGREGATE_TIE_RULE = "aggregate_tie_rule"
    COMPONENT_TIE_RULE = "component_tie_rule"
    TIMING_RULE = "timing_rule"
    CONTRIBUTION_RULE = "contribution_rule"
    PAYABLE_RULE = "payable_rule"
    COST_CENTER_RULE = "cost_center_rule"


class PayrollGlRunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CoreDifferenceType(str, Enum):
    NONE = "none"
    MISSING_IN_A = "missing_in_a"
    MISSING_IN_B = "missing_in_b"
    VALUE_MISMATCH = "value_mismatch"
    MAPPING_GAP = "mapping_gap"
    TIMING_DIFFERENCE = "timing_difference"
    CLASSIFICATION_DIFFERENCE = "classification_difference"
    FX_DIFFERENCE = "fx_difference"
    AGGREGATION_DIFFERENCE = "aggregation_difference"


class PayrollGlDifferenceType(str, Enum):
    TIMING_DIFFERENCE = "timing_difference"
    MAPPING_GAP = "mapping_gap"
    MISSING_GL_POSTING = "missing_gl_posting"
    MISSING_PAYROLL_COMPONENT = "missing_payroll_component"
    CLASSIFICATION_DIFFERENCE = "classification_difference"
    COST_CENTER_MISMATCH = "cost_center_mismatch"
    ENTITY_MISMATCH = "entity_mismatch"
    PAYABLE_MISMATCH = "payable_mismatch"
    ACCRUAL_GAP = "accrual_gap"
    ROUNDING_DIFFERENCE = "rounding_difference"
    UNSUPPORTED_SOURCE_GAP = "unsupported_source_gap"

