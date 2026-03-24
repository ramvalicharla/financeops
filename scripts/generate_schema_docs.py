from __future__ import annotations

import importlib
import inspect
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
OUTPUT_DIR = ROOT / "docs" / "schema"
OUTPUT_FILE = OUTPUT_DIR / "SCHEMA_DICTIONARY.md"

APPEND_ONLY_TABLE_HINTS = {
    "audit_trail",
    "expense_claims",
    "expense_approvals",
    "checklist_runs",
    "fdd_sections",
    "fdd_findings",
    "ppa_allocations",
    "ppa_intangibles",
    "ma_valuations",
    "ma_documents",
    "forecast_runs",
    "forecast_line_items",
    "scenario_sets",
    "scenario_results",
    "scenario_line_items",
    "budget_line_items",
    "backup_run_log",
    "compliance_events",
    "gdpr_data_requests",
    "gdpr_breach_records",
}


def _module_name_from_path(path: Path) -> str:
    relative = path.relative_to(BACKEND_DIR).with_suffix("")
    return ".".join(relative.parts)


def _prepare_env() -> None:
    os.environ["DEBUG"] = "false"
    os.environ.setdefault("SECRET_KEY", "schema-docs-secret-key-000000000000000000")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
    os.environ.setdefault("JWT_SECRET", "0123456789abcdef0123456789abcdef")
    os.environ.setdefault("FIELD_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")


def _import_model_modules() -> list[str]:
    errors: list[str] = []
    paths: list[Path] = []
    paths.extend((BACKEND_DIR / "financeops" / "db" / "models").glob("*.py"))
    paths.extend((BACKEND_DIR / "financeops" / "platform" / "db" / "models").glob("*.py"))
    paths.extend((BACKEND_DIR / "financeops" / "modules").glob("*/models.py"))
    paths.extend((BACKEND_DIR / "financeops" / "modules").glob("*/gdpr_models.py"))
    imported: set[str] = set()
    for path in sorted(item for item in paths if item.name != "__init__.py"):
        module_name = _module_name_from_path(path)
        if module_name in imported:
            continue
        imported.add(module_name)
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{module_name}: {exc}")
    return errors


def _default_for_column(column) -> str:  # type: ignore[no-untyped-def]
    if column.default is not None:
        value = getattr(column.default, "arg", None)
        if value is not None:
            return str(value)
    if column.server_default is not None:
        arg = getattr(column.server_default, "arg", None)
        if arg is not None:
            return str(arg)
    return "—"


def generate_schema_docs() -> str:
    try:
        _prepare_env()
        sys.path.insert(0, str(BACKEND_DIR))
        import_errors = _import_model_modules()
        from financeops.db.base import Base
    except Exception as exc:  # noqa: BLE001
        return f"# FinanceOps Schema Dictionary\n\nGenerated: {date.today().isoformat()}\n\nError: {exc}\n"

    mapper_by_table: dict[str, str] = {}
    for mapper in Base.registry.mappers:
        class_doc = inspect.getdoc(mapper.class_) or ""
        first_line = class_doc.splitlines()[0] if class_doc else mapper.class_.__name__
        mapper_by_table[mapper.local_table.name] = first_line

    tables = sorted(Base.metadata.tables.values(), key=lambda table: table.name)
    lines: list[str] = [
        "# FinanceOps Schema Dictionary",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "This file is auto-generated. Do not edit manually.",
        "Regenerate with: `python scripts/generate_schema_docs.py`",
        "",
        "## Tables",
        "",
    ]

    if import_errors:
        lines.extend(["### Import Warnings", ""])
        for item in import_errors:
            lines.append(f"- {item}")
        lines.extend(["", "---", ""])

    for table in tables:
        table_name = table.name
        description = mapper_by_table.get(table_name, table_name)
        has_rls = any(column.name == "tenant_id" for column in table.columns)
        is_append_only = table_name in APPEND_ONLY_TABLE_HINTS

        lines.extend(
            [
                f"### {table_name}",
                "",
                f"- **Description**: {description}",
                f"- **RLS enabled**: {'Yes' if has_rls else 'No'}",
                f"- **Append-only**: {'Yes' if is_append_only else 'No'}",
                "",
                "| Column | Type | Nullable | Default |",
                "|---|---|---|---|",
            ]
        )
        for column in table.columns:
            lines.append(
                f"| {column.name} | {column.type} | {'Yes' if column.nullable else 'No'} | {_default_for_column(column)} |"
            )

        foreign_keys = sorted(table.foreign_keys, key=lambda fk: fk.parent.name)
        if foreign_keys:
            lines.extend(["", "**Foreign keys:**"])
            for fk in foreign_keys:
                lines.append(f"- `{fk.parent.name}` -> `{fk.target_fullname}`")

        indexes = sorted(table.indexes, key=lambda idx: idx.name or "")
        if indexes:
            lines.extend(["", "**Indexes:**"])
            for index in indexes:
                columns = ", ".join(column.name for column in index.columns)
                lines.append(f"- `{index.name}` ({columns})")

        lines.extend(["", "---", ""])

    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        content = generate_schema_docs()
        OUTPUT_FILE.write_text(content, encoding="utf-8")
        print(f"Generated: {OUTPUT_FILE}")
        print(f"Tables documented: {sum(1 for line in content.splitlines() if line.startswith('### '))}")
        return 0
    except Exception as exc:  # noqa: BLE001
        fallback = (
            "# FinanceOps Schema Dictionary\n\n"
            f"Generated: {date.today().isoformat()}\n\n"
            f"Generation failed gracefully: {exc}\n"
        )
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            OUTPUT_FILE.write_text(fallback, encoding="utf-8")
        except Exception:
            pass
        print("Generated fallback schema dictionary.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
