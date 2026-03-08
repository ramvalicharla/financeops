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


class HealthClassification(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    STRESSED = "stressed"
    CRITICAL = "critical"
