from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

from financeops.prompt_engine import PromptDefinition, PytestResult


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    reason: str | None = None


class ExecutionValidator:
    def __init__(
        self,
        project_root: Path,
        *,
        pytest_timeout_seconds: int = 1200,
        run_precheck_pytest: bool = True,
    ) -> None:
        self.project_root = project_root
        self.pytest_timeout_seconds = pytest_timeout_seconds
        self.run_precheck_pytest = run_precheck_pytest

    def verify_dependencies(
        self, prompt: PromptDefinition, successful_prompt_ids: set[str]
    ) -> ValidationResult:
        missing = sorted([dep for dep in prompt.dependencies if dep not in successful_prompt_ids])
        if missing:
            return ValidationResult(
                ok=False,
                reason=(
                    f"Dependency verification failed for {prompt.prompt_id}; "
                    f"missing successful dependencies: {', '.join(missing)}"
                ),
            )
        return ValidationResult(ok=True)

    def verify_repository_health(self) -> ValidationResult:
        migration_check = self._check_incomplete_migrations()
        if not migration_check.ok:
            return migration_check
        return ValidationResult(ok=True)

    def run_pytest(self) -> PytestResult:
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["pytest", "-q"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.pytest_timeout_seconds,
                check=False,
            )
            duration = time.perf_counter() - start
            output = (proc.stdout or "") + (proc.stderr or "")
            return PytestResult(success=(proc.returncode == 0), output=output, duration_seconds=duration)
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start
            msg = f"pytest -q timed out after {self.pytest_timeout_seconds}s: {exc}"
            return PytestResult(success=False, output=msg, duration_seconds=duration)

    def maybe_run_precheck_pytest(self) -> ValidationResult:
        if not self.run_precheck_pytest:
            return ValidationResult(ok=True)
        result = self.run_pytest()
        if not result.success:
            return ValidationResult(
                ok=False,
                reason=(
                    "Repository health validation failed: baseline pytest -q is not green "
                    "before executing prompt.\n" + result.output
                ),
            )
        return ValidationResult(ok=True)

    def _check_incomplete_migrations(self) -> ValidationResult:
        migrations_root = self.project_root / "backend" / "migrations"
        if not migrations_root.exists():
            return ValidationResult(ok=True)

        markers = ("TODO", "PLACEHOLDER", "FIXME", "pass  #")
        for path in migrations_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                if marker in text:
                    rel = path.relative_to(self.project_root).as_posix()
                    return ValidationResult(
                        ok=False,
                        reason=(
                            "Repository health validation failed: incomplete migration marker "
                            f"'{marker}' found in {rel}"
                        ),
                    )
        return ValidationResult(ok=True)

