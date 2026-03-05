from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from financeops.prompt_engine.guardrails.security_policy import (
    PROMPTS_LEDGER_PATH,
    is_path_protected,
    normalize_rel_path,
)

_EXCLUDED_DIRS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
_EXCLUDED_SUFFIXES = {".pyc"}
_EXCLUDED_FILENAMES = {".finos_prompt_engine.lock"}


@dataclass(slots=True)
class FileFingerprint:
    size: int
    sha256: str
    text: str | None


@dataclass(slots=True)
class RepositoryProtectionResult:
    ok: bool
    reason: str | None = None


class RepositoryProtection:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def snapshot(self) -> dict[str, FileFingerprint]:
        snapshot: dict[str, FileFingerprint] = {}
        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue
            if self._is_excluded(path):
                continue

            rel = normalize_rel_path(path.relative_to(self.project_root))
            raw = path.read_bytes()
            text: str | None = None
            if rel == normalize_rel_path(PROMPTS_LEDGER_PATH):
                text = raw.decode("utf-8")
            snapshot[rel] = FileFingerprint(
                size=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                text=text,
            )
        return snapshot

    @staticmethod
    def diff(
        before: dict[str, FileFingerprint], after: dict[str, FileFingerprint]
    ) -> list[str]:
        changed: list[str] = []
        for path in sorted(set(before) | set(after)):
            if path not in before or path not in after:
                changed.append(path)
                continue
            if before[path].sha256 != after[path].sha256:
                changed.append(path)
        return changed

    def enforce(
        self,
        modified_files: list[str],
        *,
        before: dict[str, FileFingerprint],
        after: dict[str, FileFingerprint],
    ) -> RepositoryProtectionResult:
        normalized_prompts_ledger = normalize_rel_path(PROMPTS_LEDGER_PATH)

        for raw_path in modified_files:
            rel = normalize_rel_path(raw_path)

            if self._is_migrations_path(rel):
                return RepositoryProtectionResult(
                    ok=False,
                    reason=f"Repository protection violation: migrations are protected ({rel})",
                )

            if not is_path_protected(rel):
                continue

            if rel == normalized_prompts_ledger:
                before_text = before.get(rel).text if rel in before else ""
                after_text = after.get(rel).text if rel in after else None
                if after_text is None:
                    return RepositoryProtectionResult(
                        ok=False,
                        reason="Repository protection violation: PROMPTS_LEDGER.md was removed",
                    )
                if not after_text.startswith(before_text or ""):
                    return RepositoryProtectionResult(
                        ok=False,
                        reason="Repository protection violation: PROMPTS_LEDGER.md must be append-only",
                    )
                continue

            return RepositoryProtectionResult(
                ok=False,
                reason=f"Repository protection violation: protected file modified ({rel})",
            )

        return RepositoryProtectionResult(ok=True)

    def _is_excluded(self, path: Path) -> bool:
        if path.name in _EXCLUDED_FILENAMES:
            return True
        if path.suffix in _EXCLUDED_SUFFIXES:
            return True
        for part in path.parts:
            if part in _EXCLUDED_DIRS:
                return True
        return False

    @staticmethod
    def _is_migrations_path(rel_path: str) -> bool:
        norm = rel_path.lower()
        return norm.startswith("migrations/") or "/migrations/" in norm
