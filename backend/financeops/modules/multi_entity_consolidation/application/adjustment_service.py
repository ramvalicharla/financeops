from __future__ import annotations

from decimal import Decimal
from typing import Any


class AdjustmentService:
    def summarize_adjustments(
        self,
        *,
        consolidated_metrics: list[object] | None = None,
        intercompany_summary: dict[str, Any] | None = None,
        adjustment_rows: list[object] | None = None,
    ) -> dict[str, object]:
        del consolidated_metrics
        intercompany_summary = intercompany_summary or {}
        unmatched_items = list(intercompany_summary.get("unmatched_items") or [])
        rules = list(adjustment_rows or [])
        default_rule = self._pick_rule(rules, preferred_type="analytic_adjustment")
        reclass_rule = self._pick_rule(rules, preferred_type="presentation_reclass")

        adjustment_entries: list[dict[str, Any]] = []
        reclassification_entries: list[dict[str, Any]] = []

        for row in unmatched_items:
            classification = str(row.get("classification", "")).strip()
            residual = Decimal(str(row.get("unexplained_difference") or row.get("residual_difference_parent") or "0"))
            if classification == "timing_difference":
                rule = reclass_rule or default_rule
                reclassification_entries.append(
                    {
                        "rule_code": self._rule_code(rule),
                        "reason": "Timing difference routed to reclassification",
                        "classification": classification,
                        "entity_from": row.get("entity_from"),
                        "entity_to": row.get("entity_to"),
                        "account_code": row.get("account_code"),
                        "amount": str(residual.copy_abs()),
                        "transaction_reference": row.get("transaction_reference"),
                    }
                )
                continue

            if residual == Decimal("0"):
                residual = Decimal(str(row.get("actual_difference") or "0")).copy_abs()
            rule = default_rule or reclass_rule
            adjustment_entries.append(
                {
                    "rule_code": self._rule_code(rule),
                    "reason": "Residual intercompany mismatch requires analytical adjustment",
                    "classification": classification or "unexplained",
                    "entity_from": row.get("entity_from"),
                    "entity_to": row.get("entity_to"),
                    "account_code": row.get("account_code"),
                    "amount": str(residual.copy_abs()),
                    "transaction_reference": row.get("transaction_reference"),
                }
            )

        total_count = len(adjustment_entries) + len(reclassification_entries)
        return {
            "validation_report": {
                "status": "PASS",
                "reason": (
                    "Adjustment and reclassification entries derived from intercompany mismatches"
                    if total_count
                    else "No residual intercompany mismatches required adjustments"
                ),
            },
            "adjustment_count": total_count,
            "adjustment_entries": adjustment_entries,
            "reclassification_entries": reclassification_entries,
            "applied": total_count > 0,
        }

    def _pick_rule(self, rows: list[object], *, preferred_type: str) -> object | None:
        ordered = sorted(
            rows,
            key=lambda item: (str(getattr(item, "adjustment_code", "")), str(getattr(item, "id", ""))),
        )
        for row in ordered:
            if str(getattr(row, "adjustment_type", "")) == preferred_type:
                return row
        return ordered[0] if ordered else None

    def _rule_code(self, row: object | None) -> str:
        if row is None:
            return "adjustment_rule_unresolved"
        return str(getattr(row, "adjustment_code", "adjustment_rule_unresolved"))
