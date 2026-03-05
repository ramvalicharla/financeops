from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time

from financeops.prompt_engine import (
    ExecutionRecord,
    PromptDefinition,
    PromptStatus,
)
from financeops.prompt_engine.guardrails.ai_firewall import AIFirewall
from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer
from financeops.prompt_engine.guardrails.prompt_sanitizer import PromptSanitizer
from financeops.prompt_engine.guardrails.repository_protection import RepositoryProtection
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
from financeops.prompt_engine.prompt_runner import PromptRunner
from financeops.prompt_engine.validation import ExecutionValidator

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionTransactionResult:
    status: PromptStatus
    modified_files: list[str]
    pytest_output: str
    failure_reason: str | None = None
    notes: str = ""
    duration_seconds: float = 0.0


class ExecutionTransaction:
    def __init__(
        self,
        *,
        project_root: Path,
        prompt_runner: PromptRunner,
        validator: ExecutionValidator,
        ledger_updater: PromptLedgerUpdater,
        prompt_sanitizer: PromptSanitizer | None = None,
        ai_firewall: AIFirewall | None = None,
        repository_protection: RepositoryProtection | None = None,
        file_size_enforcer: FileSizeEnforcer | None = None,
    ) -> None:
        self.project_root = project_root
        self.prompt_runner = prompt_runner
        self.validator = validator
        self.ledger_updater = ledger_updater
        self.prompt_sanitizer = prompt_sanitizer or PromptSanitizer()
        self.ai_firewall = ai_firewall or AIFirewall()
        self.repository_protection = repository_protection or RepositoryProtection(project_root)
        self.file_size_enforcer = file_size_enforcer or FileSizeEnforcer(project_root)

    def execute(
        self,
        prompt: PromptDefinition,
        *,
        successful_prompt_ids: set[str],
        rework_attempt: int = 0,
    ) -> ExecutionTransactionResult:
        started = time.perf_counter()
        baseline_snapshot = self.repository_protection.snapshot()
        pytest_output = "N/A"
        failure_reason: str | None = None
        notes = ""

        try:
            log.info("TX phase 1/10 Load Prompt: %s", prompt.prompt_id)

            log.info("TX phase 2/10 Sanitize Prompt: %s", prompt.prompt_id)
            sanitize = self.prompt_sanitizer.sanitize(prompt.prompt_text)
            if not sanitize.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=[],
                    pytest_output=pytest_output,
                    failure_reason=sanitize.reason,
                    notes="Prompt sanitization failed",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            log.info("TX phase 3/10 AI Firewall Check: %s", prompt.prompt_id)
            firewall = self.ai_firewall.check(prompt.prompt_text)
            if not firewall.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=[],
                    pytest_output=pytest_output,
                    failure_reason=firewall.reason,
                    notes="AI firewall blocked prompt execution",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            log.info("TX phase 4/10 Dependency Verification: %s", prompt.prompt_id)
            dep_check = self.validator.verify_dependencies(prompt, successful_prompt_ids)
            if not dep_check.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=[],
                    pytest_output=pytest_output,
                    failure_reason=dep_check.reason,
                    notes="Dependency verification failed",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            log.info("TX phase 5/10 Repository Health Validation: %s", prompt.prompt_id)
            health_check = self.validator.verify_repository_health()
            if not health_check.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=[],
                    pytest_output=pytest_output,
                    failure_reason=health_check.reason,
                    notes="Repository health check failed",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            precheck = self.validator.maybe_run_precheck_pytest()
            if not precheck.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=[],
                    pytest_output=pytest_output,
                    failure_reason=precheck.reason,
                    notes="Baseline pytest precheck failed",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            log.info("TX phase 6/10 Execute Prompt: %s", prompt.prompt_id)
            run_result = self.prompt_runner.run(prompt)

            after_snapshot = self.repository_protection.snapshot()
            modified_files = self.repository_protection.diff(baseline_snapshot, after_snapshot)

            log.info("TX phase 7/10 File/Repo Guardrails: %s", prompt.prompt_id)
            repo_guard = self.repository_protection.enforce(
                modified_files, before=baseline_snapshot, after=after_snapshot
            )
            if not repo_guard.ok:
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=modified_files,
                    pytest_output=pytest_output,
                    failure_reason=repo_guard.reason,
                    notes="Repository protection violation",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            file_guard = self.file_size_enforcer.enforce(modified_files)
            if not file_guard.ok:
                summary = "; ".join(
                    f"{v.path} has {v.lines} lines (max {v.max_lines})"
                    for v in file_guard.violations
                )
                return self._finalize(
                    prompt=prompt,
                    status=PromptStatus.FAIL,
                    modified_files=modified_files,
                    pytest_output=pytest_output,
                    failure_reason=f"File size enforcement failed: {summary}",
                    notes="File modularization required before continuation",
                    rework_attempt=rework_attempt,
                    started=started,
                )

            log.info("TX phase 8/10 Run pytest: %s", prompt.prompt_id)
            pytest_result = self.validator.run_pytest()
            pytest_output = pytest_result.output

            if not run_result.completed:
                failure_reason = run_result.failure_reason or "Implementation incomplete"
                notes = "Prompt execution incomplete; rework required"
                status = PromptStatus.REWORK_REQUIRED
            elif not pytest_result.success:
                failure_reason = "pytest -q failed after prompt execution"
                notes = "Test failures detected; rework required"
                status = PromptStatus.REWORK_REQUIRED
            else:
                status = PromptStatus.SUCCESS
                notes = run_result.notes or "Prompt execution completed successfully"

            return self._finalize(
                prompt=prompt,
                status=status,
                modified_files=run_result.modified_files or modified_files,
                pytest_output=pytest_output,
                failure_reason=failure_reason,
                notes=notes,
                rework_attempt=rework_attempt,
                started=started,
            )
        except Exception as exc:
            log.exception("Execution transaction crashed for %s", prompt.prompt_id)
            return self._finalize(
                prompt=prompt,
                status=PromptStatus.FAIL,
                modified_files=[],
                pytest_output=pytest_output,
                failure_reason=f"Execution transaction exception: {exc}",
                notes="Unhandled transaction exception",
                rework_attempt=rework_attempt,
                started=started,
            )

    def _finalize(
        self,
        *,
        prompt: PromptDefinition,
        status: PromptStatus,
        modified_files: list[str],
        pytest_output: str,
        failure_reason: str | None,
        notes: str,
        rework_attempt: int,
        started: float,
    ) -> ExecutionTransactionResult:
        log.info("TX phase 9/10 Update Prompt Ledger: %s -> %s", prompt.prompt_id, status.value)
        record = ExecutionRecord(
            prompt_id=prompt.prompt_id,
            subsystem=prompt.subsystem,
            execution_status=status,
            rework_attempt_number=rework_attempt,
            files_modified=sorted(set(modified_files)),
            test_results=("PASS" if status == PromptStatus.SUCCESS else "FAIL/NOT_RUN"),
            failure_reason=failure_reason,
            notes=notes,
        )
        ledger_result = self.ledger_updater.append_execution(record)
        if not ledger_result.ok:
            status = PromptStatus.FAIL
            failure_reason = (
                "Ledger update failed; transactional success criteria not met. "
                + (ledger_result.reason or "")
            ).strip()

        duration = time.perf_counter() - started
        log.info("TX phase 10/10 Determine status: %s -> %s", prompt.prompt_id, status.value)
        return ExecutionTransactionResult(
            status=status,
            modified_files=sorted(set(modified_files)),
            pytest_output=pytest_output,
            failure_reason=failure_reason,
            notes=notes,
            duration_seconds=duration,
        )

