from __future__ import annotations

from typing import Any


class IntercompanyService:
    def classify_source_refs(self, *, source_run_refs: list[dict[str, Any]]) -> dict[str, Any]:
        # Phase 2.3 v1 keeps intercompany handling explicit and non-posting.
        return {
            "rules_evaluated": len(source_run_refs),
            "unmatched_count": 0,
            "elimination_applied": False,
        }

