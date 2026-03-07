from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from financeops.prompt_engine import PromptDefinition, PromptRunResult
from financeops.prompt_engine.prompt_runner import PromptExecutorCallback
from financeops.prompt_engine.review_gate import PatchSummary, run_review_gate

_ALLOWED_ROOTS = {"backend", "docs", "tests"}
_BLOCKED_ROOTS = {"infra", "docker", ".git"}
_DEPENDENCY_FILES = {
    "pyproject.toml",
    "poetry.lock",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}
_DEPENDENCY_GLOBS = ("requirements*.txt",)

_PATCH_LIMIT_DEFAULTS = {
    "max_files": 15,
    "max_added_lines": 400,
    "max_removed_lines": 400,
    "max_bytes": 250_000,
}
_PATCH_LIMIT_HARD_MAX = {
    "max_files": 200,
    "max_added_lines": 20_000,
    "max_removed_lines": 20_000,
    "max_bytes": 5_000_000,
}
_PATCH_LIMIT_ENV_MAP = {
    "max_files": "FINOS_PATCH_MAX_FILES",
    "max_added_lines": "FINOS_PATCH_MAX_ADDED_LINES",
    "max_removed_lines": "FINOS_PATCH_MAX_REMOVED_LINES",
    "max_bytes": "FINOS_PATCH_MAX_BYTES",
}


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


def _parse_patch_stats(patch_text: str, paths: list[str]) -> PatchSummary:
    added = 0
    removed = 0
    for line in patch_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return PatchSummary(
        changed_files=sorted(paths),
        added_lines=added,
        removed_lines=removed,
        patch_bytes=len(patch_text.encode("utf-8")),
        patch_text=patch_text,
    )


def _resolve_patch_limits() -> dict[str, int]:
    resolved: dict[str, int] = {}
    for key, default_value in _PATCH_LIMIT_DEFAULTS.items():
        env_name = _PATCH_LIMIT_ENV_MAP[key]
        hard_max = _PATCH_LIMIT_HARD_MAX[key]
        raw_value = os.getenv(env_name, "").strip()
        if raw_value:
            try:
                parsed = int(raw_value)
            except ValueError:
                parsed = default_value
        else:
            parsed = default_value
        parsed = max(1, parsed)
        parsed = min(parsed, hard_max)
        resolved[key] = parsed
    return resolved


def _check_patch_limits(summary: PatchSummary, limits: dict[str, int]) -> str | None:
    violations: list[str] = []
    if len(summary.changed_files) > limits["max_files"]:
        violations.append(
            f"files={len(summary.changed_files)}>{limits['max_files']}"
        )
    if summary.added_lines > limits["max_added_lines"]:
        violations.append(
            f"added_lines={summary.added_lines}>{limits['max_added_lines']}"
        )
    if summary.removed_lines > limits["max_removed_lines"]:
        violations.append(
            f"removed_lines={summary.removed_lines}>{limits['max_removed_lines']}"
        )
    if summary.patch_bytes > limits["max_bytes"]:
        violations.append(
            f"bytes={summary.patch_bytes}>{limits['max_bytes']}"
        )
    if not violations:
        return None
    return "PATCH_LIMIT_EXCEEDED: " + ", ".join(violations)


def _dependency_paths(paths: list[str]) -> list[str]:
    matches: list[str] = []
    for path in paths:
        normalized = PurePosixPath(path).as_posix().lower()
        filename = PurePosixPath(normalized).name
        if filename in _DEPENDENCY_FILES:
            matches.append(path)
            continue
        if any(fnmatch.fnmatch(filename, pattern) for pattern in _DEPENDENCY_GLOBS):
            matches.append(path)
    return sorted(set(matches))


@dataclass(slots=True)
class CodexRunner:
    repo_root: Path
    command: tuple[str, ...]
    timeout_seconds: int = 900
    allow_deps: bool = False
    high_risk_approved: bool = False
    enable_review_gate: bool = False

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

        patch_summary = _parse_patch_stats(patch_text, paths)
        limit_error = _check_patch_limits(patch_summary, _resolve_patch_limits())
        if limit_error:
            return PromptRunResult(completed=False, failure_reason=limit_error)

        dep_paths = _dependency_paths(paths)
        if dep_paths and not self.allow_deps:
            return PromptRunResult(
                completed=False,
                failure_reason=(
                    "DEPENDENCY_CHANGES_NOT_ALLOWED: patch touches dependency files "
                    f"({', '.join(dep_paths)}). Re-run with --allow-deps."
                ),
            )
        if dep_paths and not self.high_risk_approved:
            return PromptRunResult(
                completed=False,
                failure_reason=(
                    "HIGH_RISK_APPROVAL_REQUIRED: dependency changes require "
                    "--approve-high-risk."
                ),
            )

        review = run_review_gate(
            enabled=self.enable_review_gate,
            prompt=prompt,
            patch_summary=patch_summary,
            high_risk_approved=self.high_risk_approved,
        )
        if not review.ok:
            return PromptRunResult(
                completed=False,
                failure_reason="REVIEW_GATE_FAILED: " + "; ".join(review.reasons),
            )

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


def build_codex_runner_callback(
    repo_root: Path,
    *,
    allow_deps: bool = False,
    high_risk_approved: bool = False,
    enable_review_gate: bool = False,
) -> PromptExecutorCallback:
    command_env = os.getenv("FINOS_CODEX_COMMAND", "").strip()
    if command_env:
        command = shlex.split(command_env)
    else:
        command = ["codex", "exec", "--output-format", "patch", "--stdin"]
    return CodexRunner(
        repo_root=repo_root,
        command=tuple(command),
        allow_deps=allow_deps,
        high_risk_approved=high_risk_approved,
        enable_review_gate=enable_review_gate,
    )
