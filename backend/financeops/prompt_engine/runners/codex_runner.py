from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess

from financeops.prompt_engine import PromptDefinition, PromptRunResult
from financeops.prompt_engine.prompt_runner import PromptExecutorCallback

_ALLOWED_ROOTS = {"backend", "docs", "tests"}
_BLOCKED_ROOTS = {"infra", "docker", ".git"}


def _normalize_patch_path(raw_path: str) -> str:
    cleaned = raw_path.strip().replace("\\", "/")
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return PurePosixPath(cleaned).as_posix()


def _extract_patch_from_codex_output(output: str) -> str:
    text = output.strip()
    if not text:
        return ""

    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            patch = payload.get("patch")
            if isinstance(patch, str):
                return patch.strip()
            return ""

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    marker = "diff --git "
    if marker in text:
        text = text[text.index(marker) :].strip()
    return text


def _extract_patch_paths(patch_text: str) -> list[str]:
    paths: set[str] = set()
    for line in patch_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            value = line[4:].strip()
            if value == "/dev/null":
                continue
            paths.add(_normalize_patch_path(value))
    return sorted(paths)


def _validate_patch_paths(paths: list[str]) -> tuple[bool, str | None]:
    if not paths:
        return False, "Codex output did not include patch paths."

    for rel_path in paths:
        if rel_path.startswith("/") or rel_path.startswith("\\"):
            return False, f"Absolute path not allowed in patch: {rel_path}"

        pure = PurePosixPath(rel_path)
        if any(part == ".." for part in pure.parts):
            return False, f"Path traversal not allowed in patch: {rel_path}"

        top = pure.parts[0] if pure.parts else ""
        if pure.name == ".env" or pure.name.startswith(".env."):
            return False, f"Protected path not allowed in patch: {rel_path}"
        if any(part == ".git" for part in pure.parts):
            return False, f"Blocked path not allowed in patch: {rel_path}"
        if top in _BLOCKED_ROOTS:
            return False, f"Blocked path not allowed in patch: {rel_path}"
        if top not in _ALLOWED_ROOTS:
            return False, f"Only backend/docs/tests paths are allowed: {rel_path}"

    return True, None


@dataclass(slots=True)
class CodexRunner:
    repo_root: Path
    command: tuple[str, ...]
    timeout_seconds: int = 900

    def __call__(self, prompt: PromptDefinition) -> PromptRunResult:
        codex_result = subprocess.run(
            list(self.command),
            cwd=self.repo_root,
            input=prompt.prompt_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        if codex_result.returncode != 0:
            return PromptRunResult(
                completed=False,
                failure_reason=(
                    f"Codex CLI failed (exit={codex_result.returncode}): "
                    f"{(codex_result.stderr or '').strip()}"
                ),
                raw_output=(codex_result.stdout or "") + (codex_result.stderr or ""),
            )

        patch_text = _extract_patch_from_codex_output(codex_result.stdout or "")
        paths = _extract_patch_paths(patch_text)
        valid, reason = _validate_patch_paths(paths)
        if not valid:
            return PromptRunResult(completed=False, failure_reason=reason)

        apply_result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "--recount", "-"],
            cwd=self.repo_root,
            input=patch_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        if apply_result.returncode != 0:
            return PromptRunResult(
                completed=False,
                failure_reason=(
                    f"git apply failed (exit={apply_result.returncode}): "
                    f"{(apply_result.stderr or '').strip()}"
                ),
                raw_output=(apply_result.stdout or "") + (apply_result.stderr or ""),
            )

        return PromptRunResult(
            completed=True,
            modified_files=paths,
            notes="Codex runner applied patch via git apply.",
            raw_output=codex_result.stdout or "",
        )


def build_codex_runner_callback(repo_root: Path) -> PromptExecutorCallback:
    command_env = os.getenv("FINOS_CODEX_COMMAND", "").strip()
    if command_env:
        command = shlex.split(command_env)
    else:
        command = ["codex", "exec", "--output-format", "patch", "--stdin"]
    return CodexRunner(repo_root=repo_root, command=tuple(command))
