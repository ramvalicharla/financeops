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


class OwnershipRuleType(str, Enum):
    FULL = "full_consolidation_rule"
    PROPORTIONATE = "proportionate_consolidation_rule"
    MINORITY = "minority_interest_rule"
    EQUITY_PLACEHOLDER = "equity_attribution_placeholder"
    EXCLUSION = "ownership_exclusion_rule"
