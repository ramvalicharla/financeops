from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ci_workflow_file_exists() -> None:
    assert (ROOT / ".github" / "workflows" / "ci.yml").exists()


def test_sast_workflow_file_exists() -> None:
    assert (ROOT / ".github" / "workflows" / "sast.yml").exists()


def test_schema_check_workflow_exists() -> None:
    assert (ROOT / ".github" / "workflows" / "schema_check.yml").exists()


def test_semgrep_config_exists() -> None:
    assert (ROOT / ".semgrep.yml").exists()


def test_semgrep_config_has_float_rule() -> None:
    content = _read(ROOT / ".semgrep.yml")
    assert "no-float-in-financial-modules" in content


def test_semgrep_config_has_secret_rule() -> None:
    content = _read(ROOT / ".semgrep.yml")
    assert "no-hardcoded-secrets" in content


def test_ci_workflow_has_postgres_service() -> None:
    content = _read(ROOT / ".github" / "workflows" / "ci.yml")
    assert "postgres:16" in content


def test_dependency_matrix_workflow_exists() -> None:
    assert (ROOT / ".github" / "workflows" / "dependency_matrix.yml").exists()


def test_ci_workflow_has_frontend_build_job() -> None:
    content = _read(ROOT / ".github" / "workflows" / "ci.yml")
    assert "frontend-build" in content


def test_sast_workflow_has_semgrep_action() -> None:
    content = _read(ROOT / ".github" / "workflows" / "sast.yml")
    assert "semgrep/semgrep-action@v1" in content

