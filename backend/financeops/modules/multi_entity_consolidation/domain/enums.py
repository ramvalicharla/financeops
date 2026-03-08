from __future__ import annotations

from enum import Enum


class VersionStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RuleType(str, Enum):
    AGGREGATION = "aggregation_rule"
    INCLUSION = "inclusion_rule"
    INTERCOMPANY = "intercompany_rule"
    ADJUSTMENT = "adjustment_rule"
    OWNERSHIP_PLACEHOLDER = "ownership_placeholder"
    CURRENCY_PLACEHOLDER = "currency_placeholder"

