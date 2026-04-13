from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

PolicyRuleType = Literal[
    "intercompany_profit_elimination",
    "minority_interest_adjustment",
    "revenue_reclassification",
]


@dataclass(frozen=True, slots=True)
class Policy:
    policy_id: str
    policy_version_id: int
    effective_date: date
    rule_type: PolicyRuleType
    parameters: dict[str, Any] = field(default_factory=dict)
