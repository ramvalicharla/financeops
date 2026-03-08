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


class RateType(str, Enum):
    CLOSING = "closing"
    AVERAGE = "average"
    HISTORICAL = "historical"

