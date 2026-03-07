from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.mis_manager.domain.value_objects import SignatureBundle
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def _norm_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _hash_list(values: list[str]) -> str:
    payload = [_norm_text(value) for value in values if _norm_text(value)]
    return sha256_hex_text(canonical_json_dumps(payload))


def build_header_hash(headers: list[str]) -> str:
    return _hash_list(headers)


def build_row_signature_hash(row_labels: list[str]) -> str:
    return _hash_list(row_labels)


def build_column_signature_hash(column_order: list[str]) -> str:
    return _hash_list(column_order)


def build_section_signature_hash(section_breaks: list[str]) -> str:
    return _hash_list(section_breaks)


def build_structure_hash(
    *,
    header_hash: str,
    row_signature_hash: str,
    column_signature_hash: str,
    section_signature_hash: str,
    blank_row_density: Decimal,
    formula_density: Decimal,
) -> str:
    payload = {
        "header_hash": header_hash,
        "row_signature_hash": row_signature_hash,
        "column_signature_hash": column_signature_hash,
        "section_signature_hash": section_signature_hash,
        "blank_row_density": str(blank_row_density),
        "formula_density": str(formula_density),
    }
    return sha256_hex_text(canonical_json_dumps(payload))


def build_signature_bundle(
    *,
    headers: list[str],
    row_labels: list[str],
    column_order: list[str],
    section_breaks: list[str],
    blank_row_density: Decimal,
    formula_density: Decimal,
) -> SignatureBundle:
    header_hash = build_header_hash(headers)
    row_signature_hash = build_row_signature_hash(row_labels)
    column_signature_hash = build_column_signature_hash(column_order)
    section_signature_hash = build_section_signature_hash(section_breaks)
    structure_hash = build_structure_hash(
        header_hash=header_hash,
        row_signature_hash=row_signature_hash,
        column_signature_hash=column_signature_hash,
        section_signature_hash=section_signature_hash,
        blank_row_density=blank_row_density,
        formula_density=formula_density,
    )
    return SignatureBundle(
        header_hash=header_hash,
        row_signature_hash=row_signature_hash,
        column_signature_hash=column_signature_hash,
        section_signature_hash=section_signature_hash,
        structure_hash=structure_hash,
    )
