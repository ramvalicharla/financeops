from __future__ import annotations

import hashlib


def mask_pan(value: str) -> str:
    visible = value[-4:] if len(value) >= 4 else value
    return f"****{visible}"


def mask_bank_account(value: str) -> str:
    visible = value[-4:] if len(value) >= 4 else value
    return f"****{visible}"


def deterministic_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
