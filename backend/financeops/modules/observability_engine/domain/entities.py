from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiffSummary:
    drift_flag: bool
    summary: dict[str, Any]
