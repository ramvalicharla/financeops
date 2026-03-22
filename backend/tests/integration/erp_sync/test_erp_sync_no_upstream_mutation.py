from __future__ import annotations

import re
from pathlib import Path

import pytest


FORBIDDEN_MODULES = (
    "mis_manager",
    "reconciliation_bridge",
    "payroll_gl_normalization",
    "payroll_gl_reconciliation",
    "ratio_variance_engine",
    "financial_risk_engine",
    "anomaly_pattern_engine",
    "board_pack_narrative_engine",
    "revenue",
    "lease",
    "prepaid",
    "fixed_assets",
    "multi_entity_consolidation",
    "fx_translation_reporting",
    "ownership_consolidation",
    "cash_flow_engine",
    "equity_engine",
    "observability_engine",
)


@pytest.mark.integration
def test_erp_sync_module_does_not_import_frozen_engine_modules() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    erp_sync_root = repo_root / "financeops" / "modules" / "erp_sync"
    forbidden = "|".join(FORBIDDEN_MODULES)
    pattern = re.compile(
        rf"^\s*(from|import)\s+financeops\.modules\.({forbidden})(?:\.|\b)",
        re.MULTILINE,
    )

    violations: list[str] = []
    for file_path in sorted(erp_sync_root.rglob("*.py")):
        if "__pycache__" in file_path.parts:
            continue
        text = file_path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            violations.append(f"{file_path}:{line_no}")

    assert not violations, f"Forbidden frozen-module imports found: {violations}"
