from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

from financeops.prompt_engine import PromptDefinition
from financeops.prompt_engine.runners.codex_runner import CodexRunner


def _prompt() -> PromptDefinition:
    return PromptDefinition(
        prompt_id="FINOS-P001",
        subsystem="Prompt Engine",
        dependencies=[],
        prompt_text="Generate a minimal backend patch.",
    )


def test_codex_runner_patch_application(tmp_path: Path) -> None:
    runner = CodexRunner(
        repo_root=tmp_path,
        command=("codex", "exec", "--output-format", "patch", "--stdin"),
    )

    patch_text = "\n".join(
        [
            "diff --git a/backend/example.txt b/backend/example.txt",
            "index 0000000..1111111 100644",
            "--- a/backend/example.txt",
            "+++ b/backend/example.txt",
            "@@ -1 +1 @@",
            "-old",
            "+new",
            "",
        ]
    )

    with patch("financeops.prompt_engine.runners.codex_runner.subprocess.run") as run_mock:
        run_mock.side_effect = [
            subprocess.CompletedProcess(
                args=["codex"],
                returncode=0,
                stdout=patch_text,
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["git", "apply"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]

        result = runner(_prompt())

    assert result.completed is True
    assert result.modified_files == ["backend/example.txt"]
    assert "git apply" in result.notes
    assert run_mock.call_count == 2

    apply_kwargs = run_mock.call_args_list[1].kwargs
    assert apply_kwargs["cwd"] == tmp_path
    assert "diff --git" in apply_kwargs["input"]


def test_codex_runner_respects_guardrails(tmp_path: Path) -> None:
    runner = CodexRunner(
        repo_root=tmp_path,
        command=("codex", "exec", "--output-format", "patch", "--stdin"),
    )

    blocked_patch = "\n".join(
        [
            "diff --git a/infra/secrets.txt b/infra/secrets.txt",
            "index 0000000..1111111 100644",
            "--- a/infra/secrets.txt",
            "+++ b/infra/secrets.txt",
            "@@ -0,0 +1 @@",
            "+blocked",
            "",
        ]
    )

    with patch("financeops.prompt_engine.runners.codex_runner.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex"],
            returncode=0,
            stdout=blocked_patch,
            stderr="",
        )

        result = runner(_prompt())

    assert result.completed is False
    assert result.failure_reason is not None
    assert "Blocked path not allowed" in result.failure_reason
    assert run_mock.call_count == 1
