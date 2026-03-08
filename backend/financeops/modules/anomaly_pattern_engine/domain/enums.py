from __future__ import annotations

from enum import Enum


class DefinitionStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnomalyDomain(str, Enum):
    PROFITABILITY = "profitability"
    COST_STRUCTURE = "cost_structure"
    LIQUIDITY = "liquidity"
    WORKING_CAPITAL = "working_capital"
    LEVERAGE = "leverage"
    PAYROLL = "payroll"
    RECONCILIATION_LINKED = "reconciliation_linked"


class SeverityLevel(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PersistenceClassification(str, Enum):
    FIRST_DETECTED = "first_detected"
    RECURRING = "recurring"
    SUSTAINED = "sustained"
    ESCALATING = "escalating"
    RESOLVED = "resolved"
    REOPENED = "reopened"
