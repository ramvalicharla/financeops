from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from financeops.prompt_engine import (
    ExecutionRecord,
    PromptRunResult,
    PromptStatus,
    PytestResult,
)
from financeops.prompt_engine.cli import run_pipeline
from financeops.prompt_engine.executor import PromptExecutionEngine
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
from financeops.prompt_engine.rework_engine import ReworkContext
from financeops.prompt_engine.validation import ValidationResult


class ValidatorStub:
    def run_pytest(self) -> PytestResult:
        return PytestResult(success=True, output="ok", duration_seconds=0.01)

    def maybe_run_precheck_pytest(self) -> ValidationResult:
        return ValidationResult(ok=True)

    def verify_repository_health(self) -> ValidationResult:
        return ValidationResult(ok=True)

    def verify_dependencies(self, prompt, successful_prompt_ids):  # noqa: ANN001
        missing = [dep for dep in prompt.dependencies if dep not in successful_prompt_ids]
        if missing:
            return ValidationResult(ok=False, reason=f"missing: {missing}")
        return ValidationResult(ok=True)


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text |",
                "|---|---|---|---|",
                "| FINOS-P001 | Auth | None | Build auth |",
                "| FINOS-P002 | RBAC | FINOS-P001 | Build rbac |",
            ]
        ),
        encoding="utf-8",
    )


def _write_structured_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# FINOS Prompt Catalog",
                "",
                "PROMPT_ID: FINOS-P001",
                "SUBSYSTEM: Auth",
                "DEPENDENCIES: None",
                "",
                "PROMPT_TEXT:",
                "Placeholder prompt for initial pipeline validation.",
                "",
                "PROMPT_ID: FINOS-P002",
                "SUBSYSTEM: Multi-Tenant",
                "DEPENDENCIES: FINOS-P001",
                "",
                "PROMPT_TEXT:",
                "Placeholder prompt for tenant isolation implementation.",
                "",
                "PROMPT_ID: FINOS-P003",
                "SUBSYSTEM: RBAC",
                "DEPENDENCIES: FINOS-P002",
                "",
                "PROMPT_TEXT:",
                "Placeholder prompt for RBAC implementation.",
            ]
        ),
        encoding="utf-8",
    )


def _seed_success(ledger_path: Path, prompt_id: str, subsystem: str) -> None:
    updater = PromptLedgerUpdater(ledger_path)
    updater.append_execution(
        ExecutionRecord(
            prompt_id=prompt_id,
            subsystem=subsystem,
            execution_status=PromptStatus.SUCCESS,
            rework_attempt_number=0,
            files_modified=[],
            test_results="PASS",
            notes="seed",
        )
    )


def test_execution_pipeline_skips_successful_prompts(tmp_path: Path) -> None:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)
    _seed_success(ledger, "FINOS-P001", "Auth")

    called: list[str] = []

    def runner(prompt):  # noqa: ANN001
        called.append(prompt.prompt_id)
        return PromptRunResult(completed=True, notes="done")

    engine = PromptExecutionEngine(
        project_root=tmp_path,
        catalog_path=catalog,
        ledger_path=ledger,
        runner_callback=runner,
    )
    stub = ValidatorStub()
    engine.validator = stub  # type: ignore[assignment]
    engine.transaction.validator = stub  # type: ignore[assignment]
    engine.rework_engine.validator = stub  # type: ignore[assignment]

    summary = engine.run()
    assert summary.failed_prompt_id is None
    assert summary.skipped_success == 1
    assert summary.executed_success == 1
    assert called == ["FINOS-P002"]


def test_execution_pipeline_triggers_rework_and_recovers(tmp_path: Path) -> None:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)

    call_count = {"runner": 0}

    def runner(prompt):  # noqa: ANN001
        call_count["runner"] += 1
        if prompt.prompt_id == "FINOS-P001":
            return PromptRunResult(completed=False, failure_reason="incomplete")
        return PromptRunResult(completed=True)

    def rework_callback(context: ReworkContext) -> PromptRunResult:
        target = tmp_path / "reworked.py"
        target.write_text("# patched\n", encoding="utf-8")
        return PromptRunResult(completed=True, modified_files=["reworked.py"], notes="patched")

    engine = PromptExecutionEngine(
        project_root=tmp_path,
        catalog_path=catalog,
        ledger_path=ledger,
        runner_callback=runner,
        rework_callback=rework_callback,
    )
    stub = ValidatorStub()
    engine.validator = stub  # type: ignore[assignment]
    engine.transaction.validator = stub  # type: ignore[assignment]
    engine.rework_engine.validator = stub  # type: ignore[assignment]

    summary = engine.run()
    assert summary.failed_prompt_id is None
    assert summary.executed_success == 2
    assert call_count["runner"] == 2


def test_execution_pipeline_halts_when_stop_file_exists(tmp_path: Path) -> None:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)
    (tmp_path / ".finos_stop").write_text("", encoding="utf-8")

    called: list[str] = []

    def runner(prompt):  # noqa: ANN001
        called.append(prompt.prompt_id)
        return PromptRunResult(completed=True, notes="done")

    engine = PromptExecutionEngine(
        project_root=tmp_path,
        catalog_path=catalog,
        ledger_path=ledger,
        runner_callback=runner,
    )
    stub = ValidatorStub()
    engine.validator = stub  # type: ignore[assignment]
    engine.transaction.validator = stub  # type: ignore[assignment]
    engine.rework_engine.validator = stub  # type: ignore[assignment]

    summary = engine.run()
    assert summary.halted_by_stop_file is True
    assert summary.executed_success == 1
    assert called == ["FINOS-P001"]


def test_cli_dry_run_prints_dependency_order(tmp_path: Path, capsys) -> None:
    _write_structured_catalog(tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md")
    args = Namespace(
        command="run",
        project_root=str(tmp_path),
        catalog="docs/prompts/PROMPTS_CATALOG.md",
        ledger="docs/ledgers/PROMPTS_LEDGER.md",
        max_rework_attempts=3,
        dry_run=True,
    )

    exit_code = run_pipeline(args)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Execution Order:" in output
    assert "1. FINOS-P001 Auth" in output
    assert "2. FINOS-P002 Multi-Tenant" in output
    assert "3. FINOS-P003 RBAC" in output
    assert not (tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md").exists()
