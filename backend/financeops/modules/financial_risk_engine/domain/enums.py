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


class RiskDomain(str, Enum):
    PROFITABILITY = "profitability"
    LIQUIDITY = "liquidity"
    LEVERAGE = "leverage"
    WORKING_CAPITAL = "working_capital"
    COST_STRUCTURE = "cost_structure"
    PAYROLL = "payroll"
    CONFIDENCE = "confidence"
    RECONCILIATION_DEPENDENCY = "reconciliation_dependency"
    BOARD_CRITICAL = "board_critical"


class SeverityLevel(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PersistenceState(str, Enum):
    NEW = "new"
    REPEATED = "repeated"
    ESCALATING = "escalating"
    DEESCALATING = "deescalating"
    RESOLVED = "resolved"
    REOPENED = "reopened"
