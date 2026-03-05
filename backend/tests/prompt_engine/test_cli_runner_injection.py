from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from financeops.prompt_engine import PytestResult
from financeops.prompt_engine.cli import run_pipeline
from financeops.prompt_engine.validation import ExecutionValidator


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text |",
                "|---|---|---|---|",
                "| FINOS-P001 | Auth | None | Placeholder prompt for local runner backend testing. |",
            ]
        ),
        encoding="utf-8",
    )


def _ledger_rows_for_prompt(ledger_path: Path, prompt_id: str) -> list[list[str]]:
    rows: list[list[str]] = []
    if not ledger_path.exists():
        return rows
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0] == prompt_id:
            rows.append(cells)
    return rows


@pytest.fixture
def force_green_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run_pytest(self) -> PytestResult:  # noqa: ANN001
        return PytestResult(success=True, output="ok", duration_seconds=0.01)

    monkeypatch.setattr(ExecutionValidator, "run_pytest", _run_pytest)


def test_cli_runner_local_executes_prompt_successfully(tmp_path: Path, force_green_pytest: None) -> None:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)

    args = Namespace(
        command="run",
        project_root=str(tmp_path),
        catalog="docs/prompts/PROMPTS_CATALOG.md",
        ledger="docs/ledgers/PROMPTS_LEDGER.md",
        max_rework_attempts=3,
        dry_run=False,
        runner="local",
    )
    exit_code = run_pipeline(args)
    assert exit_code == 0

    artifact = (
        tmp_path
        / "backend"
        / "financeops"
        / "prompt_engine"
        / "_runner_artifacts"
        / "FINOS-P001.txt"
    )
    assert artifact.exists()

    rows = _ledger_rows_for_prompt(ledger, "FINOS-P001")
    statuses = [row[3] for row in rows]
    assert statuses[0] == "RUNNING"
    assert statuses[-1] == "SUCCESS"


def test_cli_runner_missing_preserves_existing_behavior(
    tmp_path: Path,
    force_green_pytest: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FINOS_PROMPT_RUNNER", raising=False)

    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)

    args = Namespace(
        command="run",
        project_root=str(tmp_path),
        catalog="docs/prompts/PROMPTS_CATALOG.md",
        ledger="docs/ledgers/PROMPTS_LEDGER.md",
        max_rework_attempts=1,
        dry_run=False,
        runner=None,
    )
    exit_code = run_pipeline(args)
    assert exit_code == 1

    rows = _ledger_rows_for_prompt(ledger, "FINOS-P001")
    statuses = [row[3] for row in rows]
    reasons = [row[7] for row in rows if len(row) > 7]
    assert "REWORK_REQUIRED" in statuses
    assert any("No prompt execution backend configured. Provide a PromptRunner callback." in reason for reason in reasons)


def test_cli_runner_codex_executes_prompt_successfully(
    tmp_path: Path,
    force_green_pytest: None,
) -> None:
    catalog = tmp_path / "docs" / "prompts" / "PROMPTS_CATALOG.md"
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    _write_catalog(catalog)

    codex_patch = "\n".join(
        [
            "diff --git a/backend/financeops/prompt_engine/_runner_artifacts/FINOS-P001.txt b/backend/financeops/prompt_engine/_runner_artifacts/FINOS-P001.txt",
            "--- a/backend/financeops/prompt_engine/_runner_artifacts/FINOS-P001.txt",
            "+++ b/backend/financeops/prompt_engine/_runner_artifacts/FINOS-P001.txt",
            "@@ -0,0 +1 @@",
            "+ok",
        ]
    )

    with patch("financeops.prompt_engine.runners.codex_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            subprocess.CompletedProcess(
                args=["codex"],
                returncode=0,
                stdout=codex_patch,
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["git", "apply"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]

        args = Namespace(
            command="run",
            project_root=str(tmp_path),
            catalog="docs/prompts/PROMPTS_CATALOG.md",
            ledger="docs/ledgers/PROMPTS_LEDGER.md",
            max_rework_attempts=3,
            dry_run=False,
            runner="codex",
        )
        exit_code = run_pipeline(args)

    assert exit_code == 0
    assert run_mock.call_count == 2

    rows = _ledger_rows_for_prompt(ledger, "FINOS-P001")
    statuses = [row[3] for row in rows]
    assert statuses[0] == "RUNNING"
    assert statuses[-1] == "SUCCESS"
