from __future__ import annotations

from argparse import Namespace
from pathlib import Path

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
                "| FINOS-P001 | Auth | None | Placeholder prompt for root resolution integration. |",
            ]
        ),
        encoding="utf-8",
    )


@pytest.fixture
def force_green_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run_pytest(self) -> PytestResult:  # noqa: ANN001
        return PytestResult(success=True, output="ok", duration_seconds=0.01)

    monkeypatch.setattr(ExecutionValidator, "run_pytest", _run_pytest)


def test_cli_run_from_repo_root_resolves_artifacts_and_ledger(
    tmp_path: Path,
    force_green_pytest: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    (backend_dir / "financeops").mkdir(parents=True, exist_ok=True)
    _write_catalog(repo_root / "docs" / "prompts" / "PROMPTS_CATALOG.md")

    monkeypatch.chdir(repo_root)
    args = Namespace(
        command="run",
        project_root=".",
        catalog="docs/prompts/PROMPTS_CATALOG.md",
        ledger="docs/ledgers/PROMPTS_LEDGER.md",
        max_rework_attempts=1,
        dry_run=False,
        runner="local",
    )

    exit_code = run_pipeline(args)
    assert exit_code == 0

    assert (
        repo_root
        / "backend"
        / "financeops"
        / "prompt_engine"
        / "_runner_artifacts"
        / "FINOS-P001.txt"
    ).exists()
    assert (repo_root / "docs" / "ledgers" / "PROMPTS_LEDGER.md").exists()
    assert not (repo_root / "backend" / "docs" / "ledgers" / "PROMPTS_LEDGER.md").exists()


def test_cli_run_from_backend_resolves_artifacts_and_ledger(
    tmp_path: Path,
    force_green_pytest: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    (backend_dir / "financeops").mkdir(parents=True, exist_ok=True)
    _write_catalog(repo_root / "docs" / "prompts" / "PROMPTS_CATALOG.md")

    monkeypatch.chdir(backend_dir)
    args = Namespace(
        command="run",
        project_root=".",
        catalog="../docs/prompts/PROMPTS_CATALOG.md",
        ledger="docs/ledgers/PROMPTS_LEDGER.md",
        max_rework_attempts=1,
        dry_run=False,
        runner="local",
    )

    exit_code = run_pipeline(args)
    assert exit_code == 0

    assert (
        repo_root
        / "backend"
        / "financeops"
        / "prompt_engine"
        / "_runner_artifacts"
        / "FINOS-P001.txt"
    ).exists()
    assert (repo_root / "docs" / "ledgers" / "PROMPTS_LEDGER.md").exists()
    assert not (repo_root / "backend" / "docs" / "ledgers" / "PROMPTS_LEDGER.md").exists()
