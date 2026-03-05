from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
import time

from financeops.prompt_engine import (
    ExecutionRecord,
    PromptDefinition,
    PromptRunResult,
    PromptStatus,
)
from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer
from financeops.prompt_engine.guardrails.repository_protection import RepositoryProtection
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
from financeops.prompt_engine.validation import ExecutionValidator

log = logging.getLogger(__name__)

ReworkCallback = Callable[["ReworkContext"], PromptRunResult]


@dataclass(slots=True)
class ReworkContext:
    prompt: PromptDefinition
    attempt_number: int
    pytest_output: str
    failing_tests: list[str]
    previously_modified_files: list[str]
    patch_instructions: str


@dataclass(slots=True)
class ReworkAttemptResult:
    status: PromptStatus
    attempt_number: int
    modified_files: list[str]
    pytest_output: str
    failure_reason: str | None = None
    notes: str = ""
    duration_seconds: float = 0.0


class ReworkEngine:
    def __init__(
        self,
        *,
        project_root: Path,
        validator: ExecutionValidator,
        repository_protection: RepositoryProtection,
        file_size_enforcer: FileSizeEnforcer,
        ledger_updater: PromptLedgerUpdater,
        max_attempts: int = 3,
        callback: ReworkCallback | None = None,
    ) -> None:
        self.project_root = project_root
        self.validator = validator
        self.repository_protection = repository_protection
        self.file_size_enforcer = file_size_enforcer
        self.ledger_updater = ledger_updater
        self.max_attempts = max_attempts
        self.callback = callback

    def run_attempt(
        self,
        *,
        prompt: PromptDefinition,
        attempt_number: int,
        pytest_output: str,
        previous_modified_files: list[str],
    ) -> ReworkAttemptResult:
        started = time.perf_counter()
        before_snapshot = self.repository_protection.snapshot()
        failing_tests = self.analyze_pytest_failures(pytest_output)
        patch_instructions = self.generate_patch_instructions(
            prompt=prompt, failing_tests=failing_tests, pytest_output=pytest_output
        )

        if self.callback is None:
            result = ReworkAttemptResult(
                status=PromptStatus.REWORK_REQUIRED,
                attempt_number=attempt_number,
                modified_files=previous_modified_files,
                pytest_output=pytest_output,
                failure_reason="No AI rework callback configured",
                notes="Rework engine unavailable",
                duration_seconds=time.perf_counter() - started,
            )
            self._append_ledger(prompt, result)
            return result

        context = ReworkContext(
            prompt=prompt,
            attempt_number=attempt_number,
            pytest_output=pytest_output,
            failing_tests=failing_tests,
            previously_modified_files=previous_modified_files,
            patch_instructions=patch_instructions,
        )

        callback_result = self.callback(context)
        after_snapshot = self.repository_protection.snapshot()
        modified_files = self.repository_protection.diff(before_snapshot, after_snapshot)
        if callback_result.modified_files:
            modified_files = sorted(set(modified_files + callback_result.modified_files))

        guard = self.repository_protection.enforce(
            modified_files, before=before_snapshot, after=after_snapshot
        )
        if not guard.ok:
            result = ReworkAttemptResult(
                status=PromptStatus.FAIL,
                attempt_number=attempt_number,
                modified_files=modified_files,
                pytest_output=pytest_output,
                failure_reason=guard.reason,
                notes="Rework failed repository protection",
                duration_seconds=time.perf_counter() - started,
            )
            self._append_ledger(prompt, result)
            return result

        file_guard = self.file_size_enforcer.enforce(modified_files)
        if not file_guard.ok:
            reason = "; ".join(
                f"{v.path} has {v.lines} lines (max {v.max_lines})"
                for v in file_guard.violations
            )
            result = ReworkAttemptResult(
                status=PromptStatus.FAIL,
                attempt_number=attempt_number,
                modified_files=modified_files,
                pytest_output=pytest_output,
                failure_reason=f"File size enforcement failed during rework: {reason}",
                notes="Rework violated modularization constraints",
                duration_seconds=time.perf_counter() - started,
            )
            self._append_ledger(prompt, result)
            return result

        pytest_result = self.validator.run_pytest()
        if callback_result.completed and pytest_result.success:
            status = PromptStatus.SUCCESS
            reason = None
            notes = "Rework succeeded"
        else:
            status = PromptStatus.REWORK_REQUIRED
            reason = callback_result.failure_reason or "Rework did not resolve failing tests"
            notes = "Rework requires another attempt"

        result = ReworkAttemptResult(
            status=status,
            attempt_number=attempt_number,
            modified_files=modified_files,
            pytest_output=pytest_result.output,
            failure_reason=reason,
            notes=notes,
            duration_seconds=time.perf_counter() - started,
        )
        self._append_ledger(prompt, result)
        return result

    @staticmethod
    def analyze_pytest_failures(pytest_output: str) -> list[str]:
        failures: list[str] = []
        for line in pytest_output.splitlines():
            stripped = line.strip()
            if stripped.startswith("FAILED "):
                failures.append(stripped.replace("FAILED ", "", 1))
        return failures

    @staticmethod
    def generate_patch_instructions(
        *, prompt: PromptDefinition, failing_tests: list[str], pytest_output: str
    ) -> str:
        tests = ", ".join(failing_tests) if failing_tests else "unknown failing tests"
        tail = "\n".join(pytest_output.splitlines()[-20:])
        return (
            f"Prompt {prompt.prompt_id} ({prompt.subsystem}) failed tests: {tests}.\n"
            "Repair only changed code paths related to these failures.\n"
            "Keep tenant isolation, idempotency, and append-only governance intact.\n"
            "Do not modify protected repository paths.\n"
            f"Failure log tail:\n{tail}"
        )

    def _append_ledger(self, prompt: PromptDefinition, result: ReworkAttemptResult) -> None:
        record = ExecutionRecord(
            prompt_id=prompt.prompt_id,
            subsystem=prompt.subsystem,
            execution_status=result.status,
            rework_attempt_number=result.attempt_number,
            files_modified=result.modified_files,
            test_results="PASS" if result.status == PromptStatus.SUCCESS else "FAIL",
            failure_reason=result.failure_reason,
            notes=result.notes,
        )
        ledger_result = self.ledger_updater.append_execution(record)
        if not ledger_result.ok:
            log.error(
                "Failed to append rework ledger entry for %s attempt %d: %s",
                prompt.prompt_id,
                result.attempt_number,
                ledger_result.reason,
            )

