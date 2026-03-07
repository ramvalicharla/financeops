from __future__ import annotations

from uuid import UUID

from financeops.core.exceptions import ValidationError

_PREFIX_MAP: dict[str, str] = {
    "REV": "REV-",
    "LSE": "LSE-",
    "PPD": "PPD-",
    "FAR": "FAR-",
    "REVENUE": "REV-",
    "LEASE": "LSE-",
    "PREPAID": "PPD-",
    "FIXED_ASSETS": "FAR-",
}


def build_journal_prefix(engine_namespace: str) -> str:
    normalized = engine_namespace.strip().upper()
    prefix = _PREFIX_MAP.get(normalized)
    if prefix is None:
        raise ValidationError("Unsupported journal namespace")
    return prefix


def build_journal_reference(
    *,
    engine_namespace: str,
    run_id: UUID,
    sequence: int,
) -> str:
    if sequence <= 0:
        raise ValidationError("Journal sequence must be positive")
    prefix = build_journal_prefix(engine_namespace)
    run_token = str(run_id).replace("-", "")[:12].upper()
    return f"{prefix}{run_token}-{sequence:06d}"
