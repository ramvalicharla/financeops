from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from financeops.prompt_engine import PromptDefinition, PromptRunResult
from financeops.prompt_engine.prompt_runner import PromptExecutorCallback

_MAX_PROMPT_PREVIEW = 120


def _safe_prompt_id(prompt_id: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", prompt_id.strip())
    return sanitized or "UNKNOWN_PROMPT"


@dataclass(slots=True)
class LocalRunner:
    project_root: Path

    def __call__(self, prompt: PromptDefinition) -> PromptRunResult:
        """
        Offline deterministic runner.

        Creates a simple artifact proving the prompt executed.
        No network calls.
        No repository modification outside artifact folder.
        """

        artifact_dir = (
            self.project_root / "financeops" / "prompt_engine" / "_runner_artifacts"
        )

        artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_name = f"{_safe_prompt_id(prompt.prompt_id)}.txt"
        artifact_file = artifact_dir / artifact_name

        timestamp = datetime.now(timezone.utc).isoformat()
        preview = " ".join(prompt.prompt_text.split())[:_MAX_PROMPT_PREVIEW]

        artifact_file.write_text(
            "\n".join(
                [
                    f"timestamp_utc={timestamp}",
                    f"prompt_id={prompt.prompt_id}",
                    f"subsystem={prompt.subsystem}",
                    f"prompt_preview={preview}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        artifact_rel = artifact_file.relative_to(self.project_root).as_posix()

        return PromptRunResult(
            completed=True,
            modified_files=[artifact_rel],
            notes="Local runner executed prompt via offline artifact write.",
        )


def build_local_runner_callback(project_root: Path) -> PromptExecutorCallback:
    runner = LocalRunner(project_root=project_root)
    return runner
