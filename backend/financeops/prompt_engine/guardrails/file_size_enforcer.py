from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FileSizeViolation:
    path: str
    lines: int
    max_lines: int
    split_suggestion: dict[str, str]


@dataclass(slots=True)
class FileSizeCheckResult:
    ok: bool
    violations: list[FileSizeViolation] = field(default_factory=list)


class FileSizeEnforcer:
    def __init__(self, project_root: Path, max_file_lines: int = 500) -> None:
        self.project_root = project_root
        self.max_file_lines = max_file_lines

    def enforce(self, modified_files: list[str]) -> FileSizeCheckResult:
        violations: list[FileSizeViolation] = []
        for rel_path in modified_files:
            abs_path = self.project_root / rel_path
            if not abs_path.exists() or not abs_path.is_file():
                continue

            line_count = self._line_count(abs_path)
            if line_count <= self.max_file_lines:
                continue

            violations.append(
                FileSizeViolation(
                    path=rel_path,
                    lines=line_count,
                    max_lines=self.max_file_lines,
                    split_suggestion=self._split_suggestion(rel_path),
                )
            )

        return FileSizeCheckResult(ok=not violations, violations=violations)

    @staticmethod
    def _line_count(path: Path) -> int:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)

    @staticmethod
    def _split_suggestion(rel_path: str) -> dict[str, str]:
        base = Path(rel_path)
        stem = base.stem
        parent = str(base.parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        prefix = f"{parent}/" if parent else ""
        return {
            "service_module": f"{prefix}{stem}_service.py",
            "router_module": f"{prefix}{stem}_router.py",
            "schema_module": f"{prefix}{stem}_schema.py",
            "utility_module": f"{prefix}{stem}_utils.py",
        }

