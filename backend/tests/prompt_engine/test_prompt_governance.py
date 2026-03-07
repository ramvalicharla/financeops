from __future__ import annotations

from pathlib import Path

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


def _write_catalog(path: Path, *, risk: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text | Risk |",
                "|---|---|---|---|---|",
                f"| FINOS-P001 | Auth | None | Build auth safely | {risk} |",
            ]
        ),
        encoding="utf-8",
    )


def _build_engine(tmp_path: Path, *, risk: str, approve_high_risk: bool) -> tuple[PromptExecutionEngine, list[str]]:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog, risk=risk)

    called: list[str] = []

    def runner(prompt):  # noqa: ANN001
        called.append(prompt.prompt_id)
        return PromptRunResult(completed=True, notes="ok")

    engine = PromptExecutionEngine(
        project_root=tmp_path,
        catalog_path=catalog,
        ledger_path=ledger,
        runner_callback=runner,
        approve_high_risk=approve_high_risk,
    )
    stub = ValidatorStub()
    engine.validator = stub  # type: ignore[assignment]
    engine.transaction.validator = stub  # type: ignore[assignment]
    engine.rework_engine.validator = stub  # type: ignore[assignment]
    return engine, called


def test_high_prompt_blocked_without_approval(tmp_path: Path) -> None:
    engine, called = _build_engine(tmp_path, risk="HIGH", approve_high_risk=False)
    summary = engine.run()
    assert summary.failed_prompt_id == "FINOS-P001"
    assert called == []


def test_medium_prompt_allowed(tmp_path: Path) -> None:
    engine, called = _build_engine(tmp_path, risk="MEDIUM", approve_high_risk=False)
    summary = engine.run()
    assert summary.failed_prompt_id is None
    assert summary.executed_success == 1
    assert called == ["FINOS-P001"]
