from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_generator_runs_without_error() -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs")
    result = module.generate_schema_docs()
    assert isinstance(result, str)
    assert result
    assert "FinanceOps Schema Dictionary" in result


def test_schema_docs_contains_key_tables() -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs_tables")
    result = module.generate_schema_docs()
    for table_name in [
        "iam_users",
        "iam_tenants",
        "audit_trail",
        "expense_claims",
        "fdd_engagements",
        "budget_line_items",
    ]:
        assert table_name in result


def test_schema_output_file_created(tmp_path: Path) -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs_output")
    content = module.generate_schema_docs()
    output = tmp_path / "SCHEMA_DICTIONARY.md"
    output.write_text(content, encoding="utf-8")
    assert output.exists()
    assert output.stat().st_size > 0


def test_all_financial_tables_documented() -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs_financial")
    result = module.generate_schema_docs()
    assert "expense_claims" in result
    assert "budget_line_items" in result
    assert "fdd_findings" in result


def test_rls_tables_marked_correctly() -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs_rls")
    result = module.generate_schema_docs()
    assert "| tenant_id |" in result


def test_dependency_matrix_script_exists() -> None:
    assert (ROOT / "scripts" / "generate_dependency_matrix.py").exists()


def test_dependency_matrix_generates_output() -> None:
    module = _load_module(ROOT / "scripts" / "generate_dependency_matrix.py", "generate_dependency_matrix")
    output = module.generate_matrix()
    assert "# Dependency Matrix" in output
    assert "Python Dependencies" in output
    assert "Node Dependencies" in output


def test_schema_docs_script_exists() -> None:
    assert (ROOT / "scripts" / "generate_schema_docs.py").exists()


def test_schema_docs_includes_service_registry_tables() -> None:
    module = _load_module(ROOT / "scripts" / "generate_schema_docs.py", "generate_schema_docs_service_registry")
    result = module.generate_schema_docs()
    assert "module_registry" in result
    assert "task_registry" in result


def test_dependency_matrix_mentions_system_dependencies() -> None:
    module = _load_module(ROOT / "scripts" / "generate_dependency_matrix.py", "generate_dependency_matrix_system")
    output = module.generate_matrix()
    assert "System Dependencies" in output

