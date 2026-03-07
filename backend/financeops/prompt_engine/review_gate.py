from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Protocol

from financeops.prompt_engine import PromptDefinition

_ALLOWED_ROOTS = {"backend", "docs", "tests"}
_SECURITY_SENSITIVE_PATH_PREFIXES = (
    "backend/financeops/prompt_engine/guardrails/",
    "backend/financeops/prompt_engine/runners/codex_runner.py",
    "backend/financeops/prompt_engine/review_gate.py",
)
_DISABLE_TEST_PATTERNS = (
    "continue-on-error: true",
    "pytest -q || true",
    "pytest --maxfail=0",
)


class ReviewStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(slots=True)
class PatchSummary:
    changed_files: list[str]
    added_lines: int
    removed_lines: int
    patch_bytes: int
    patch_text: str = ""


@dataclass(slots=True)
class ReviewDecision:
    status: ReviewStatus
    reasons: list[str] = field(default_factory=list)
    severity: str = "LOW"

    @property
    def ok(self) -> bool:
        return self.status == ReviewStatus.PASS


class ReviewPlugin(Protocol):
    def review(
        self,
        *,
        prompt: PromptDefinition,
        patch_summary: PatchSummary,
    ) -> ReviewDecision:
        ...


def run_review_gate(
    *,
    enabled: bool,
    prompt: PromptDefinition,
    patch_summary: PatchSummary,
    high_risk_approved: bool,
    plugins: list[ReviewPlugin] | None = None,
) -> ReviewDecision:
    if not enabled:
        return ReviewDecision(status=ReviewStatus.PASS, reasons=[], severity="LOW")

    reasons: list[str] = []
    severity = "LOW"

    for path in patch_summary.changed_files:
        normalized = str(PurePosixPath(path.replace("\\", "/")))
        top = PurePosixPath(normalized).parts[0] if PurePosixPath(normalized).parts else ""
        if top not in _ALLOWED_ROOTS:
            reasons.append(f"Review gate blocked path outside allowed roots: {normalized}")
            severity = "HIGH"

        if normalized.startswith(_SECURITY_SENSITIVE_PATH_PREFIXES) and not high_risk_approved:
            reasons.append(
                "Review gate blocked security-sensitive prompt engine change "
                f"without high-risk approval: {normalized}"
            )
            severity = "HIGH"

    deleted_tests = _deleted_test_paths(patch_summary.patch_text)
    if deleted_tests and not high_risk_approved:
        reasons.append(
            "Review gate blocked test deletion without high-risk approval: "
            + ", ".join(sorted(deleted_tests))
        )
        severity = "HIGH"

    if _contains_disable_test_patterns(patch_summary.patch_text):
        reasons.append("Review gate blocked patch containing test-disable patterns in CI config")
        severity = "HIGH"

    for plugin in plugins or []:
        plugin_decision = plugin.review(prompt=prompt, patch_summary=patch_summary)
        if not plugin_decision.ok:
            reasons.extend(plugin_decision.reasons)
            if plugin_decision.severity == "HIGH":
                severity = "HIGH"

    if reasons:
        return ReviewDecision(
            status=ReviewStatus.FAIL,
            reasons=sorted(set(reasons)),
            severity=severity,
        )
    return ReviewDecision(status=ReviewStatus.PASS, reasons=[], severity=severity)


def _deleted_test_paths(patch_text: str) -> list[str]:
    deleted: set[str] = set()
    current_path = ""
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                current_path = parts[3].replace("b/", "", 1)
        if line.strip() == "deleted file mode 100644" and (
            current_path.startswith("tests/") or current_path.startswith("backend/tests/")
        ):
            deleted.add(current_path)
        if line.startswith("--- ") and "/tests/" in line.replace("\\", "/") and " /dev/null" not in line:
            normalized = line[4:].strip().replace("a/", "", 1).replace("\\", "/")
            if normalized.startswith("tests/") or normalized.startswith("backend/tests/"):
                deleted.add(normalized)
    return sorted(deleted)


def _contains_disable_test_patterns(patch_text: str) -> bool:
    lower_text = patch_text.lower()
    if ".github/workflows/" not in lower_text and "ci" not in lower_text:
        return False
    return any(pattern in lower_text for pattern in _DISABLE_TEST_PATTERNS)
