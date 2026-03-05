from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path

from financeops.prompt_engine import ExecutionRecord, PromptDefinition, PromptStatus
from financeops.prompt_engine.dependency_graph import DependencyGraph
from financeops.prompt_engine.execution_transaction import (
    ExecutionTransaction,
    ExecutionTransactionResult,
)
from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer
from financeops.prompt_engine.guardrails.repository_protection import RepositoryProtection
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
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
    ) -> None:
        self.project_root = project_root
        self.catalog_path = catalog_path
        self.ledger_path = ledger_path
        self.max_rework_attempts = max_rework_attempts
        self.stop_file = self.project_root / ".finos_stop"

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
