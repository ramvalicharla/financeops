from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.services.consolidation.elimination_engine import build_elimination_decisions
from financeops.services.consolidation.ic_matcher import (
    IntercompanyToleranceConfig,
    IntercompanyMatchDecision,
    MatchCandidateLine,
    match_intercompany_lines,
)
from financeops.services.consolidation.service_types import (
    DEFAULT_AMOUNT_TOLERANCE_PARENT,
    DEFAULT_FX_EXPLAINED_TOLERANCE_PARENT,
    DEFAULT_TIMING_TOLERANCE_DAYS,
)


class IntercompanyService:
    # DEPRECATED: direct matcher/elimination calls should be routed through this facade.
    def classify_source_refs(
        self,
        *,
        source_run_refs: list[dict[str, Any]],
        metric_rows: list[object] | None = None,
        intercompany_rules: list[object] | None = None,
    ) -> dict[str, Any]:
        candidate_result = self._build_candidates(metric_rows=metric_rows or [])
        if candidate_result["status"] == "no_data":
            return self._empty_contract(reason="no intercompany transactions")

        candidates = candidate_result["candidates"]
        if not candidates:
            return self._empty_contract(reason="no intercompany transactions")

        tolerance = self._resolve_tolerance(intercompany_rules=intercompany_rules or [])
        return self._legacy_matcher_contract(
            candidates=candidates,
            tolerance=tolerance,
            rules_evaluated=len(intercompany_rules or source_run_refs),
        )

    def match_candidates(
        self,
        *,
        candidates: list[MatchCandidateLine],
        tolerance: IntercompanyToleranceConfig,
    ) -> dict[str, Any]:
        if not candidates:
            return self._empty_contract(reason="no intercompany transactions")
        return self._legacy_matcher_contract(
            candidates=candidates,
            tolerance=tolerance,
            rules_evaluated=0,
        )

    def build_eliminations_from_pairs(
        self,
        *,
        pair_rows: list[object],
        tolerance: IntercompanyToleranceConfig,
    ) -> dict[str, Any]:
        if not pair_rows:
            return self._empty_contract(reason="no intercompany transactions")

        decisions = [
            IntercompanyMatchDecision(
                match_key_hash=str(row.match_key_hash),
                entity_from=row.entity_from,
                entity_to=row.entity_to,
                account_code=str(row.account_code),
                ic_reference=row.ic_reference,
                amount_local_from=Decimal(str(row.amount_local_from)),
                amount_local_to=Decimal(str(row.amount_local_to)),
                amount_parent_from=Decimal(str(row.amount_parent_from)),
                amount_parent_to=Decimal(str(row.amount_parent_to)),
                expected_difference=Decimal(str(row.expected_difference)),
                actual_difference=Decimal(str(row.actual_difference)),
                fx_explained=Decimal(str(row.fx_explained)),
                unexplained_difference=Decimal(str(row.unexplained_difference)),
                classification=str(row.classification),
                transaction_date_from=None,
                transaction_date_to=None,
            )
            for row in pair_rows
        ]
        pair_ids = {str(row.match_key_hash): row.id for row in pair_rows}
        elimination_decisions = build_elimination_decisions(pair_ids=pair_ids, pairs=decisions)
        return self._build_contract(
            decisions=decisions,
            elimination_decisions=elimination_decisions,
            pair_ids=pair_ids,
            tolerance=tolerance,
            rules_evaluated=0,
        )

    def _build_candidates(self, *, metric_rows: list[object]) -> dict[str, Any]:
        candidates: list[MatchCandidateLine] = []
        errors: list[str] = []
        intercompany_signals = 0
        for row in metric_rows:
            dimension_json = dict(getattr(row, "dimension_json", {}) or {})
            source_summary_json = dict(getattr(row, "source_summary_json", {}) or {})
            scope_json = dimension_json.get("scope")
            if not isinstance(scope_json, dict):
                scope_json = {}

            ic_reference = self._first_text(
                source_summary_json.get("ic_reference"),
                dimension_json.get("ic_reference"),
                scope_json.get("ic_reference"),
            )
            counterparty_entity = self._first_uuid(
                source_summary_json.get("ic_counterparty_entity"),
                source_summary_json.get("counterparty_entity"),
                dimension_json.get("ic_counterparty_entity"),
                dimension_json.get("counterparty_entity"),
                scope_json.get("counterparty_entity"),
            )
            ic_account_class = self._first_text(
                source_summary_json.get("ic_account_class"),
                dimension_json.get("ic_account_class"),
                scope_json.get("ic_account_class"),
            )

            if any([ic_reference, counterparty_entity, ic_account_class]):
                intercompany_signals += 1
            if not any([ic_reference, counterparty_entity, ic_account_class]):
                continue

            entity_id = self._first_uuid(
                dimension_json.get("entity_id"),
                dimension_json.get("legal_entity"),
                scope_json.get("entity_id"),
                scope_json.get("entity"),
            )
            if entity_id is None:
                errors.append(f"{getattr(row, 'id', 'unknown')}: missing entity reference")
                continue

            account_code = self._first_text(
                source_summary_json.get("account_code"),
                dimension_json.get("account_code"),
                scope_json.get("account_code"),
                getattr(row, "metric_code", None),
            )
            if account_code is None:
                errors.append(f"{getattr(row, 'id', 'unknown')}: missing account code")
                continue

            transaction_date = self._first_date(
                source_summary_json.get("transaction_date"),
                source_summary_json.get("posting_date"),
            )

            metric_value = Decimal(str(getattr(row, "metric_value")))
            candidates.append(
                MatchCandidateLine(
                    snapshot_line_id=getattr(row, "id"),
                    entity_id=entity_id,
                    account_code=account_code,
                    local_amount=self._first_decimal(
                        source_summary_json.get("local_amount"),
                        metric_value,
                    ),
                    expected_rate=self._first_decimal(
                        source_summary_json.get("expected_rate"),
                        Decimal("1.000000"),
                    ),
                    parent_amount=self._first_decimal(
                        source_summary_json.get("parent_amount"),
                        metric_value,
                    ),
                    ic_reference=ic_reference,
                    ic_counterparty_entity=counterparty_entity,
                    transaction_date=transaction_date,
                    ic_account_class=ic_account_class,
                )
            )

        if errors:
            raise ValueError(
                "validation_report.status=FAIL: invalid intercompany source rows: "
                + "; ".join(errors)
            )
        if not candidates and intercompany_signals == 0:
            return {"status": "no_data", "candidates": []}
        return {"status": "ok", "candidates": candidates}

    def _resolve_tolerance(
        self, *, intercompany_rules: list[object]
    ) -> IntercompanyToleranceConfig:
        amount_tolerance = DEFAULT_AMOUNT_TOLERANCE_PARENT
        fx_tolerance = DEFAULT_FX_EXPLAINED_TOLERANCE_PARENT
        timing_tolerance_days = DEFAULT_TIMING_TOLERANCE_DAYS
        for row in sorted(
            intercompany_rules,
            key=lambda item: (str(getattr(item, "rule_code", "")), str(getattr(item, "id", ""))),
        ):
            treatment_rule_json = dict(getattr(row, "treatment_rule_json", {}) or {})
            if "amount_tolerance_parent" in treatment_rule_json:
                amount_tolerance = Decimal(str(treatment_rule_json["amount_tolerance_parent"]))
            if "fx_explained_tolerance_parent" in treatment_rule_json:
                fx_tolerance = Decimal(str(treatment_rule_json["fx_explained_tolerance_parent"]))
            if "timing_tolerance_days" in treatment_rule_json:
                timing_tolerance_days = int(treatment_rule_json["timing_tolerance_days"])
        return IntercompanyToleranceConfig(
            amount_tolerance_parent=amount_tolerance,
            fx_explained_tolerance_parent=fx_tolerance,
            timing_tolerance_days=timing_tolerance_days,
        )

    def _legacy_matcher_contract(
        self,
        *,
        candidates: list[MatchCandidateLine],
        tolerance: IntercompanyToleranceConfig,
        rules_evaluated: int,
    ) -> dict[str, Any]:
        decisions = match_intercompany_lines(lines=candidates, tolerance=tolerance)
        if not decisions:
            return self._empty_contract(reason="no intercompany transactions")

        pair_ids = {
            row.match_key_hash: uuid.uuid5(uuid.NAMESPACE_URL, row.match_key_hash) for row in decisions
        }
        elimination_decisions = build_elimination_decisions(pair_ids=pair_ids, pairs=decisions)
        return self._build_contract(
            decisions=decisions,
            elimination_decisions=elimination_decisions,
            pair_ids=pair_ids,
            tolerance=tolerance,
            rules_evaluated=rules_evaluated,
        )

    def _build_contract(
        self,
        *,
        decisions: list[IntercompanyMatchDecision],
        elimination_decisions: list[object],
        pair_ids: dict[str, uuid.UUID],
        tolerance: IntercompanyToleranceConfig,
        rules_evaluated: int,
    ) -> dict[str, Any]:
        matched_pairs = []
        unmatched_items = []
        for row in decisions:
            payload = {
                "match_key_hash": row.match_key_hash,
                "entity_from": str(row.entity_from),
                "entity_to": str(row.entity_to),
                "account_code": row.account_code,
                "ic_reference": row.ic_reference,
                "amount_local_from": str(row.amount_local_from),
                "amount_local_to": str(row.amount_local_to),
                "amount_parent_from": str(row.amount_parent_from),
                "amount_parent_to": str(row.amount_parent_to),
                "classification": row.classification,
                "expected_difference": str(row.expected_difference),
                "actual_difference": str(row.actual_difference),
                "fx_explained": str(row.fx_explained),
                "unexplained_difference": str(row.unexplained_difference),
                "transaction_reference": row.ic_reference or row.match_key_hash,
                "transaction_date_from": (
                    row.transaction_date_from.isoformat()
                    if row.transaction_date_from is not None
                    else None
                ),
                "transaction_date_to": (
                    row.transaction_date_to.isoformat()
                    if row.transaction_date_to is not None
                    else None
                ),
                "matching_rationale": f"legacy_matcher:{row.classification}",
                "tolerance_applied": self._tolerance_payload(tolerance),
            }
            if row.classification in {"matched", "fx_explained"}:
                matched_pairs.append(payload)
            else:
                unmatched_items.append(payload)

        pair_reference_map = {
            str(pair_ids[row.match_key_hash]): row.ic_reference or row.match_key_hash for row in decisions
        }
        elimination_entries = [
            {
                "intercompany_pair_id": str(row.intercompany_pair_id),
                "entity_from": str(row.entity_from),
                "entity_to": str(row.entity_to),
                "account_code": row.account_code,
                "classification_at_time": row.classification_at_time,
                "elimination_status": row.elimination_status,
                "eliminated_amount_parent": str(row.eliminated_amount_parent),
                "fx_component_impact_parent": str(row.fx_component_impact_parent),
                "residual_difference_parent": str(row.residual_difference_parent),
                "rule_code": row.rule_code,
                "reason": row.reason,
                "transaction_reference": pair_reference_map.get(str(row.intercompany_pair_id)),
                "matching_rationale": row.reason,
                "tolerance_applied": self._tolerance_payload(tolerance),
            }
            for row in elimination_decisions
        ]

        return {
            "rules_evaluated": rules_evaluated,
            "validation_report": {
                "status": "PASS",
                "reason": "Legacy intercompany matcher and elimination engine applied",
            },
            "matched_pairs": matched_pairs,
            "unmatched_items": unmatched_items,
            "elimination_entries": elimination_entries,
            "matched_pair_count": len(matched_pairs),
            "unmatched_count": len(unmatched_items),
            "elimination_count": len(elimination_entries),
            "elimination_applied": any(
                row["elimination_status"] == "applied" for row in elimination_entries
            ),
        }

    def _empty_contract(self, *, reason: str) -> dict[str, Any]:
        return {
            "rules_evaluated": 0,
            "validation_report": {
                "status": "PASS",
                "reason": reason,
            },
            "matched_pairs": [],
            "unmatched_items": [],
            "elimination_entries": [],
            "matched_pair_count": 0,
            "unmatched_count": 0,
            "elimination_count": 0,
            "elimination_applied": False,
        }

    def _tolerance_payload(self, tolerance: IntercompanyToleranceConfig) -> dict[str, Any]:
        return {
            "amount_tolerance_parent": str(tolerance.amount_tolerance_parent),
            "fx_explained_tolerance_parent": str(tolerance.fx_explained_tolerance_parent),
            "timing_tolerance_days": tolerance.timing_tolerance_days,
        }

    def _first_text(self, *values: Any) -> str | None:
        for value in values:
            text = str(value).strip() if value is not None else ""
            if text:
                return text
        return None

    def _first_uuid(self, *values: Any) -> uuid.UUID | None:
        for value in values:
            if value is None or value == "":
                continue
            try:
                return uuid.UUID(str(value))
            except (TypeError, ValueError):
                continue
        return None

    def _first_decimal(self, *values: Any) -> Decimal:
        for value in values:
            if value is None:
                continue
            try:
                return Decimal(str(value))
            except Exception:
                continue
        raise ValueError("validation_report.status=FAIL: missing decimal value for intercompany line")

    def _first_date(self, *values: Any) -> date | None:
        for value in values:
            if value is None or value == "":
                continue
            try:
                return date.fromisoformat(str(value))
            except ValueError:
                continue
        return None
