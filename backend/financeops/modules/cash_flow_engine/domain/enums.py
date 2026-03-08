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


class MethodType(str, Enum):
    INDIRECT = "indirect"
    DIRECT = "direct"
