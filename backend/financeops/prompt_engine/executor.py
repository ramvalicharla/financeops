from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock, Timeout

from financeops.prompt_engine import ExecutionRecord, PromptDefinition, PromptStatus
from financeops.prompt_engine.dependency_graph import DependencyGraph
from financeops.prompt_engine.execution_transaction import (
    ExecutionTransaction,
    ExecutionTransactionResult,
)
from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer
from financeops.prompt_engine.guardrails.repository_protection import (
    RepositoryProtection,
)
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
from financeops.prompt_engine.prompt_governance import evaluate_prompt_approval
from financeops.prompt_engine.prompt_loader import PromptLoader
from financeops.prompt_engine.prompt_runner import PromptRunner
from financeops.prompt_engine.rework_engine import ReworkCallback, ReworkEngine
from financeops.prompt_engine.validation import ExecutionValidator

log = logging.getLogger(__name__)


@dataclass(slots=True)
class PromptExecutionSummary:
    total_prompts: int
    skipped_success: int
    executed_success: int
    failed_prompt_id: str | None
    halted_by_stop_file: bool
    details: dict[str, PromptStatus] = field(default_factory=dict)


class PromptExecutionEngine:
    def __init__(
        self,
        *,
        project_root: Path,
        catalog_path: Path,
        ledger_path: Path,
        runner_callback=None,
        rework_callback: ReworkCallback | None = None,
        max_rework_attempts: int = 3,
        approve_high_risk: bool = False,
        approval_token: str | None = None,
        allow_ledger_repair: bool = False,
    ) -> None:
        self.project_root = project_root
        self.catalog_path = catalog_path
        self.ledger_path = ledger_path
        self.max_rework_attempts = max_rework_attempts
        self.stop_file = self.project_root / ".finos_stop"
        self.execution_lock_path = self.project_root / ".finos_prompt_engine.lock"
        self.approve_high_risk = approve_high_risk
        self.approval_token = approval_token
        self.allow_ledger_repair = allow_ledger_repair

        self.loader = PromptLoader(catalog_path)
        self.ledger_updater = PromptLedgerUpdater(ledger_path)
        self.validator = ExecutionValidator(project_root)
        self.repository_protection = RepositoryProtection(project_root)
        self.file_size_enforcer = FileSizeEnforcer(project_root)
        self.prompt_runner = PromptRunner(callback=runner_callback)
        self.transaction = ExecutionTransaction(
            project_root=project_root,
            prompt_runner=self.prompt_runner,
            validator=self.validator,
            ledger_updater=self.ledger_updater,
            repository_protection=self.repository_protection,
            file_size_enforcer=self.file_size_enforcer,
        )
        self.rework_engine = ReworkEngine(
            project_root=project_root,
            validator=self.validator,
            repository_protection=self.repository_protection,
            file_size_enforcer=self.file_size_enforcer,
            ledger_updater=self.ledger_updater,
            max_attempts=max_rework_attempts,
            callback=rework_callback,
        )

    def run(self) -> PromptExecutionSummary:
        self._cleanup_stale_execution_lock()
        lock = FileLock(str(self.execution_lock_path))
        try:
            with lock.acquire(timeout=0):
                return self._run_unlocked()
        except Timeout:
            log.warning("Prompt engine execution blocked: another runner is active")
            return PromptExecutionSummary(
                total_prompts=0,
                skipped_success=0,
                executed_success=0,
                failed_prompt_id=None,
                halted_by_stop_file=False,
                details={},
            )

    def _cleanup_stale_execution_lock(self) -> None:
        if not self.execution_lock_path.exists():
            return

        lock = FileLock(str(self.execution_lock_path))
        try:
            with lock.acquire(timeout=0):
                try:
                    self.execution_lock_path.unlink(missing_ok=True)
                except OSError:
                    log.debug(
                        "Unable to remove stale execution lock file: %s",
                        self.execution_lock_path,
                    )
        except Timeout:
            # Active lock held by another process; do not remove.
            return

    def _run_unlocked(self) -> PromptExecutionSummary:
        integrity = self.ledger_updater.verify_hash_chain()
        if not integrity.ok:
            if self.allow_ledger_repair:
                repair = self.ledger_updater.repair_hash_chain()
                if not repair.ok:
                    log.error("Ledger repair failed: %s", repair.reason)
                    return PromptExecutionSummary(
                        total_prompts=0,
                        skipped_success=0,
                        executed_success=0,
                        failed_prompt_id="LEDGER_REPAIR_FAILED",
                        halted_by_stop_file=False,
                        details={},
                    )
                integrity = self.ledger_updater.verify_hash_chain()
            if not integrity.ok:
                log.error("Ledger integrity verification failed: %s", integrity.reason)
                return PromptExecutionSummary(
                    total_prompts=0,
                    skipped_success=0,
                    executed_success=0,
                    failed_prompt_id="LEDGER_INTEGRITY",
                    halted_by_stop_file=False,
                    details={},
                )

        catalog = self.loader.load()
        order = DependencyGraph(catalog.prompts).topological_order()
        status_map = self.ledger_updater.latest_status_map()
        successful = self.ledger_updater.successful_prompts(status_map)

        skipped_success = 0
        executed_success = 0
        failed_prompt_id: str | None = None
        halted_by_stop_file = False
        details = self.ledger_updater.statuses_for(order, status_map)

        for prompt in order:
            if prompt.prompt_id in successful:
                skipped_success += 1
                details[prompt.prompt_id] = PromptStatus.SUCCESS
                log.info("Skipping %s (already SUCCESS in ledger)", prompt.prompt_id)
                continue

            governance = evaluate_prompt_approval(
                prompt,
                approve_high_risk=self.approve_high_risk,
                approval_token=self.approval_token,
            )
            if not governance.allowed:
                failed_prompt_id = prompt.prompt_id
                details[prompt.prompt_id] = PromptStatus.FAIL
                self.ledger_updater.append_execution(
                    ExecutionRecord(
                        prompt_id=prompt.prompt_id,
                        subsystem=prompt.subsystem,
                        execution_status=PromptStatus.FAIL,
                        rework_attempt_number=0,
                        files_modified=[],
                        test_results="FAIL/NOT_RUN",
                        failure_reason=governance.reason,
                        notes="Prompt governance blocked execution",
                    )
                )
                log.error(governance.reason)
                break

            log.info("Prompt start: %s (%s)", prompt.prompt_id, prompt.subsystem)
            running_append = self.ledger_updater.append_running(prompt)
            if not running_append.ok:
                failed_prompt_id = prompt.prompt_id
                details[prompt.prompt_id] = PromptStatus.FAIL
                log.error("Unable to append RUNNING status for %s: %s", prompt.prompt_id, running_append.reason)
                break

            tx_result = self.transaction.execute(
                prompt, successful_prompt_ids=successful, rework_attempt=0
            )
            details[prompt.prompt_id] = tx_result.status
            self._log_completion(prompt, tx_result)

            if tx_result.status == PromptStatus.SUCCESS:
                successful.add(prompt.prompt_id)
                executed_success += 1
            elif tx_result.status == PromptStatus.REWORK_REQUIRED:
                rework_ok = self._run_rework_loop(
                    prompt=prompt,
                    previous=tx_result,
                    successful=successful,
                    details=details,
                )
                if rework_ok:
                    executed_success += 1
                else:
                    failed_prompt_id = prompt.prompt_id
                    break
            else:
                failed_prompt_id = prompt.prompt_id
                break

            if self.stop_file.exists():
                halted_by_stop_file = True
                log.warning("Execution halted by operator (.finos_stop detected)")
                break

        return PromptExecutionSummary(
            total_prompts=len(order),
            skipped_success=skipped_success,
            executed_success=executed_success,
            failed_prompt_id=failed_prompt_id,
            halted_by_stop_file=halted_by_stop_file,
            details=details,
        )

    def _run_rework_loop(
        self,
        *,
        prompt: PromptDefinition,
        previous: ExecutionTransactionResult,
        successful: set[str],
        details: dict[str, PromptStatus],
    ) -> bool:
        pytest_output = previous.pytest_output
        modified_files = previous.modified_files

        for attempt in range(1, self.max_rework_attempts + 1):
            log.info("Rework attempt %d/%d for %s", attempt, self.max_rework_attempts, prompt.prompt_id)
            result = self.rework_engine.run_attempt(
                prompt=prompt,
                attempt_number=attempt,
                pytest_output=pytest_output,
                previous_modified_files=modified_files,
            )
            details[prompt.prompt_id] = result.status

            if result.status == PromptStatus.SUCCESS:
                successful.add(prompt.prompt_id)
                log.info("Rework succeeded for %s on attempt %d", prompt.prompt_id, attempt)
                return True
            if result.status == PromptStatus.FAIL:
                log.error("Rework hard-failed for %s on attempt %d: %s", prompt.prompt_id, attempt, result.failure_reason)
                return False

            pytest_output = result.pytest_output
            modified_files = result.modified_files

        exhausted_record = ExecutionRecord(
            prompt_id=prompt.prompt_id,
            subsystem=prompt.subsystem,
            execution_status=PromptStatus.FAIL,
            rework_attempt_number=self.max_rework_attempts,
            files_modified=modified_files,
            test_results="FAIL",
            failure_reason=(
                f"Rework attempts exhausted ({self.max_rework_attempts}) "
                "without achieving SUCCESS"
            ),
            notes="Pipeline stopped after max rework attempts",
        )
        self.ledger_updater.append_execution(exhausted_record)
        details[prompt.prompt_id] = PromptStatus.FAIL
        log.error("Rework exhausted for %s; pipeline will stop", prompt.prompt_id)
        return False

    @staticmethod
    def _log_completion(prompt: PromptDefinition, result: ExecutionTransactionResult) -> None:
        log.info(
            "Prompt completion: %s status=%s duration=%.2fs",
            prompt.prompt_id,
            result.status.value,
            result.duration_seconds,
        )
        if result.failure_reason:
            log.warning("Prompt %s reason: %s", prompt.prompt_id, result.failure_reason)
