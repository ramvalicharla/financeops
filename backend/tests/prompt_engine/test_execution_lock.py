from __future__ import annotations

import logging
from pathlib import Path

from filelock import FileLock
import pytest

from financeops.prompt_engine import PromptRunResult, PytestResult
from financeops.prompt_engine.executor import PromptExecutionEngine
from financeops.prompt_engine.validation import ValidationResult


class ValidatorStub:
    def run_pytest(self) -> PytestResult:
        return PytestResult(success=True, output="ok", duration_seconds=0.01)

    def maybe_run_precheck_pytest(self) -> ValidationResult:
        return ValidationResult(ok=True)

    def verify_repository_health(self) -> ValidationResult:
        return ValidationResult(ok=True)

    def verify_dependencies(self, prompt, successful_prompt_ids):  # noqa: ANN001
        return ValidationResult(ok=True)


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text |",
                "|---|---|---|---|",
                "| FINOS-P001 | Auth | None | Build auth |",
            ]
        ),
        encoding="utf-8",
    )


def _build_engine(tmp_path: Path, runner) -> PromptExecutionEngine:  # noqa: ANN001
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)

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
    return engine


def test_second_execution_blocked_by_global_lock(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    called: list[str] = []

    def runner(prompt):  # noqa: ANN001
        called.append(prompt.prompt_id)
        return PromptRunResult(completed=True, notes="done")

    engine = _build_engine(tmp_path, runner)
    lock = FileLock(str(tmp_path / ".finos_prompt_engine.lock"))

    caplog.set_level(logging.WARNING)
    with lock.acquire(timeout=0):
        summary = engine.run()

    assert summary.total_prompts == 0
    assert summary.executed_success == 0
    assert summary.failed_prompt_id is None
    assert called == []
    assert "Prompt engine execution blocked: another runner is active" in caplog.text


def test_lock_released_after_successful_run(tmp_path: Path) -> None:
    def runner(prompt):  # noqa: ANN001
        return PromptRunResult(completed=True, notes="done")

    engine = _build_engine(tmp_path, runner)
    summary = engine.run()
    assert summary.failed_prompt_id is None
    assert summary.executed_success == 1

    lock = FileLock(str(tmp_path / ".finos_prompt_engine.lock"))
    with lock.acquire(timeout=0):
        assert True


def test_lock_released_after_exception(tmp_path: Path) -> None:
    def runner(prompt):  # noqa: ANN001
        return PromptRunResult(completed=True, notes="done")

    engine = _build_engine(tmp_path, runner)
    engine.loader.load = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="boom"):
        engine.run()

    lock = FileLock(str(tmp_path / ".finos_prompt_engine.lock"))
    with lock.acquire(timeout=0):
        assert True
