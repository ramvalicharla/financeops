from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from financeops.utils import determinism


@dataclass
class _DbCompat:
    """
    Compatibility shim for legacy ERP utility imports.

    FinanceOps does not ship a local sqlite job DB, so get_conn() is intentionally
    unavailable outside that environment.
    """

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    @contextmanager
    def get_conn() -> Iterator[Any]:
        raise RuntimeError(
            "Local job database helpers are unavailable in FinanceOps runtime. "
            "Use FinanceOps repositories/services instead of compatibility DB helpers."
        )
        yield  # pragma: no cover


db = _DbCompat()

__all__ = ["db", "determinism"]
