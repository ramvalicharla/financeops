from __future__ import annotations

from typing import Any

from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def _canonicalize_for_signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize_for_signature(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        normalized_items = [_canonicalize_for_signature(item) for item in value]
        # Make request signatures order-insensitive for semantically unordered lists.
        return sorted(normalized_items, key=canonical_json_dumps)
    if isinstance(value, tuple):
        normalized_items = [_canonicalize_for_signature(item) for item in value]
        return sorted(normalized_items, key=canonical_json_dumps)
    return value


def build_request_signature(payload: dict[str, Any]) -> str:
    canonical_payload = _canonicalize_for_signature(payload)
    return sha256_hex_text(canonical_json_dumps(canonical_payload))

