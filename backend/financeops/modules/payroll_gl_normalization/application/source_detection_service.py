from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.payroll_gl_normalization.infrastructure.structure_signature_builder import (
    build_structure_signature,
)


class SourceDetectionService:
    def detect(
        self,
        *,
        headers: list[str],
        row_labels: list[str],
        blank_row_density: Decimal,
        formula_density: Decimal,
        source_family_hint: str | None,
    ) -> dict[str, Any]:
        source_family = self._infer_source_family(headers, source_family_hint)
        signature = build_structure_signature(
            headers=headers,
            row_labels=row_labels,
            source_family=source_family,
            blank_row_density=blank_row_density,
            formula_density=formula_density,
        )
        summary = {
            "source_family": source_family,
            "headers": headers,
            "row_count": len(row_labels),
            "blank_row_density": str(blank_row_density),
            "formula_density": str(formula_density),
        }
        return {
            "source_family": source_family,
            "signature": {
                "structure_hash": signature.structure_hash,
                "header_hash": signature.header_hash,
                "row_signature_hash": signature.row_signature_hash,
            },
            "detection_summary_json": summary,
        }

    def _infer_source_family(
        self, headers: list[str], source_family_hint: str | None
    ) -> str:
        if source_family_hint in {"payroll", "gl", "erp_gl_api", "payroll_provider_export"}:
            return source_family_hint
        normalized = {str(item).strip().lower() for item in headers if str(item).strip()}
        payroll_markers = {"employee", "gross", "net", "salary", "allowance", "deduction"}
        gl_markers = {"account", "debit", "credit", "journal", "posting", "document"}
        if any(any(marker in name for marker in payroll_markers) for name in normalized):
            return "payroll"
        if any(any(marker in name for marker in gl_markers) for name in normalized):
            return "gl"
        return "gl"
