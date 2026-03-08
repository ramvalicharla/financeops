from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def build_token(
    payload: Mapping[str, Any],
    *,
    sorted_list_fields: Iterable[str] = (),
) -> str:
    normalized = dict(payload)
    for key in sorted_list_fields:
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = sorted(value)
    return sha256_hex_text(canonical_json_dumps(normalized))


def build_version_rows_token(rows: list[dict[str, Any]]) -> str:
    return sha256_hex_text(canonical_json_dumps(rows))
