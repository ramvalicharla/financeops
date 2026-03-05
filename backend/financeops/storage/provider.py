from __future__ import annotations

from financeops.storage.r2 import R2Storage

_storage: R2Storage | None = None


def get_storage() -> R2Storage:
    global _storage
    if _storage is None:
        _storage = R2Storage()
    return _storage
