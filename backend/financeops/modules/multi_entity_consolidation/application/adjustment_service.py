from __future__ import annotations


class AdjustmentService:
    def summarize_adjustments(self) -> dict[str, object]:
        # Phase 2.3 v1 uses analytical hooks only. No posting or engine mutation.
        return {
            "adjustment_count": 0,
            "applied": False,
        }

