from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from financeops.prompt_engine import PromptDefinition
from financeops.prompt_engine.runners.codex_runner import CodexRunner


def _prompt() -> PromptDefinition:
    return PromptDefinition(
        prompt_id="FINOS-P001",
        subsystem="Prompt Engine",
        dependencies=[],
        prompt_text="Update dependencies",
        risk="MEDIUM",
    )


def test_dependency_file_change_blocked_without_allow_deps(tmp_path: Path) -> None:
    runner = CodexRunner(
        repo_root=tmp_path,
        command=("codex", "exec", "--output-format", "patch", "--stdin"),
        allow_deps=False,
        high_risk_approved=False,
    )

    dep_patch = "\n".join(
        [
            "diff --git a/backend/pyproject.toml b/backend/pyproject.toml",
            "--- a/backend/pyproject.toml",
            "+++ b/backend/pyproject.toml",
            "@@ -1 +1 @@",
            "+dependency change",
            "",
        ]
    )

    with patch("financeops.prompt_engine.runners.codex_runner.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex"],
            returncode=0,
            stdout=dep_patch,
            stderr="",
        )
        result = runner(_prompt())

    assert result.completed is False
    assert result.failure_reason is not None
    assert "DEPENDENCY_CHANGES_NOT_ALLOWED" in result.failure_reason
    assert run_mock.call_count == 1
