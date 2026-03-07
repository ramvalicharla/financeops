from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from financeops.prompt_engine import PromptDefinition
from financeops.prompt_engine.runners.codex_runner import CodexRunner


def _prompt() -> PromptDefinition:
    return PromptDefinition(
        prompt_id="FINOS-P001",
        subsystem="Prompt Engine",
        dependencies=[],
        prompt_text="Create a patch",
    )


def test_patch_limits_reject_large_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CodexRunner(
        repo_root=tmp_path,
        command=("codex", "exec", "--output-format", "patch", "--stdin"),
    )
    monkeypatch.setenv("FINOS_PATCH_MAX_ADDED_LINES", "1")

    patch_text = "\n".join(
        [
            "diff --git a/backend/example.txt b/backend/example.txt",
            "--- a/backend/example.txt",
            "+++ b/backend/example.txt",
            "@@ -0,0 +3 @@",
            "+line-1",
            "+line-2",
            "+line-3",
            "",
        ]
    )

    with patch("financeops.prompt_engine.runners.codex_runner.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex"],
            returncode=0,
            stdout=patch_text,
            stderr="",
        )
        result = runner(_prompt())

    assert result.completed is False
    assert result.failure_reason is not None
    assert "PATCH_LIMIT_EXCEEDED" in result.failure_reason
    assert run_mock.call_count == 1
