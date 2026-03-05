from __future__ import annotations

from pathlib import Path

from financeops.prompt_engine import PromptDefinition, PromptRunResult, PytestResult, PromptStatus
from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer
from financeops.prompt_engine.guardrails.repository_protection import RepositoryProtection
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater
from financeops.prompt_engine.rework_engine import ReworkContext, ReworkEngine


class DummyValidator:
    def __init__(self, success: bool) -> None:
        self.success = success

    def run_pytest(self) -> PytestResult:
        return PytestResult(
            success=self.success,
            output="pytest output",
            duration_seconds=0.1,
        )


def test_rework_engine_succeeds_when_callback_repairs(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("# PROMPTS_LEDGER\n", encoding="utf-8")
    target = tmp_path / "module.py"
    target.write_text("before\n", encoding="utf-8")

    def callback(context: ReworkContext) -> PromptRunResult:
        target.write_text("after\n", encoding="utf-8")
        return PromptRunResult(completed=True, modified_files=["module.py"], notes="fixed")

    engine = ReworkEngine(
        project_root=tmp_path,
        validator=DummyValidator(success=True),  # type: ignore[arg-type]
        repository_protection=RepositoryProtection(tmp_path),
        file_size_enforcer=FileSizeEnforcer(tmp_path),
        ledger_updater=PromptLedgerUpdater(ledger),
        callback=callback,
    )

    prompt = PromptDefinition("FINOS-P001", "Auth", [], "prompt")
    result = engine.run_attempt(
        prompt=prompt,
        attempt_number=1,
        pytest_output="FAILED test_a.py::test_case",
        previous_modified_files=[],
    )
    assert result.status == PromptStatus.SUCCESS
    assert "module.py" in result.modified_files


def test_rework_engine_requires_callback(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("# PROMPTS_LEDGER\n", encoding="utf-8")

    engine = ReworkEngine(
        project_root=tmp_path,
        validator=DummyValidator(success=False),  # type: ignore[arg-type]
        repository_protection=RepositoryProtection(tmp_path),
        file_size_enforcer=FileSizeEnforcer(tmp_path),
        ledger_updater=PromptLedgerUpdater(ledger),
        callback=None,
    )
    prompt = PromptDefinition("FINOS-P001", "Auth", [], "prompt")
    result = engine.run_attempt(
        prompt=prompt,
        attempt_number=1,
        pytest_output="FAILED test_x.py::test_fail",
        previous_modified_files=[],
    )
    assert result.status == PromptStatus.REWORK_REQUIRED

