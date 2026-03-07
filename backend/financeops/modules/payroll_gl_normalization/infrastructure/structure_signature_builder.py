from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.payroll_gl_normalization.domain.entities import (
    StructureSignatureBundle,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _hash_list(values: list[str]) -> str:
    cleaned = [_norm(item) for item in values if _norm(item)]
    return sha256_hex_text(canonical_json_dumps(cleaned))


def build_structure_signature(
    *,
    headers: list[str],
    row_labels: list[str],
    source_family: str,
    blank_row_density: Decimal,
    formula_density: Decimal,
) -> StructureSignatureBundle:
    header_hash = _hash_list(headers)
    row_signature_hash = _hash_list(row_labels)
    structure_hash = sha256_hex_text(
        canonical_json_dumps(
            {
                "source_family": source_family,
                "header_hash": header_hash,
                "row_signature_hash": row_signature_hash,
                "blank_row_density": str(blank_row_density),
                "formula_density": str(formula_density),
            }
        )
    )
    return StructureSignatureBundle(
        structure_hash=structure_hash,
        header_hash=header_hash,
        row_signature_hash=row_signature_hash,
        detection_summary_json={},
    )
