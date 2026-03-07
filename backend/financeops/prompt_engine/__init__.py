from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum


class PromptStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    REWORK_REQUIRED = "REWORK_REQUIRED"


@dataclass(slots=True)
class PromptDefinition:
    prompt_id: str
    subsystem: str
    dependencies: list[str]
    prompt_text: str
    title: str = ""
    risk: str = "MEDIUM"
    description: str = ""
    acceptance_criteria: str = ""
    files_expected: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptRunResult:
    completed: bool
    modified_files: list[str] = field(default_factory=list)
    notes: str = ""
    failure_reason: str | None = None
    raw_output: str = ""


@dataclass(slots=True)
class PytestResult:
    success: bool
    output: str
    duration_seconds: float


@dataclass(slots=True)
class ExecutionRecord:
    prompt_id: str
    subsystem: str
    execution_status: PromptStatus
    rework_attempt_number: int
    files_modified: list[str]
    test_results: str
    failure_reason: str | None = None
    notes: str = ""
    execution_timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
