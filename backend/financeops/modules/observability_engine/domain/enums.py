from __future__ import annotations

from enum import Enum


class OperationType(str, Enum):
    DIFF = "diff"
    REPLAY_VALIDATE = "replay_validate"
    GRAPH_SNAPSHOT = "graph_snapshot"
    DEPENDENCY_EXPLORE = "dependency_explore"
    REGISTRY_SYNC = "registry_sync"


class OperationStatus(str, Enum):
    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"
