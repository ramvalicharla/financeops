from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from financeops.accounting_policy_engine.models import Policy, PolicyRuleType
from financeops.accounting_policy_engine.policy_rules import (
    default_policies,
    intercompany_policy_input_rules,
    minority_interest_policy_input_rules,
    policy_audit_trace,
    revenue_policy_input_rules,
)
from financeops.config import settings
from financeops.data_quality_engine import DataQualityValidationService


class AccountingPolicyService:
    def __init__(
        self,
        *,
        policies: Iterable[Policy] | None = None,
        validation_service: DataQualityValidationService | None = None,
    ) -> None:
        self._policies = tuple(policies) if policies is not None else ()
        self._default_policies = default_policies()
        self._validation = validation_service or DataQualityValidationService()

    def resolve_policy(
        self,
        *,
        rule_type: PolicyRuleType,
        current_date: date,
        policies: Iterable[Policy] | None = None,
    ) -> Policy:
        selected, _, _ = self._resolve_policy_entry(
            rule_type=rule_type,
            current_date=current_date,
            policies=policies,
        )
        return selected

    def apply_intercompany_profit_elimination_policy(
        self,
        *,
        elimination_entries: list[dict[str, Any]],
        current_date: date,
        policies: Iterable[Policy] | None = None,
    ) -> dict[str, Any]:
        policy, policy_source, source_reason = self._resolve_policy_entry(
            rule_type="intercompany_profit_elimination",
            current_date=current_date,
            policies=policies,
        )
        validation = self._validation.validate_dataset(
            rules=intercompany_policy_input_rules(),
            rows=elimination_entries,
        )
        self._validation.raise_if_fail(report=validation)

        rate = self._decimal_param(policy, "unrealized_profit_rate")
        applied_entries: list[dict[str, Any]] = []
        affected_entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        for row in self._sorted_dicts(
            elimination_entries,
            keys=("intercompany_pair_id", "transaction_reference", "account_code"),
        ):
            before_amount = Decimal(str(row.get("eliminated_amount_parent", "0")))
            profit_adjustment = (
                before_amount.copy_abs() * rate
            ).quantize(Decimal("0.000000"))
            signed_adjustment = profit_adjustment if before_amount >= 0 else -profit_adjustment
            after_amount = (before_amount - signed_adjustment).quantize(Decimal("0.000000"))
            updated = dict(row)
            updated["eliminated_amount_parent"] = str(after_amount)
            updated["policy_rule_type"] = "intercompany_profit_elimination"
            updated["policy_adjustment_amount"] = str(profit_adjustment)
            updated["policy_id"] = policy.policy_id
            updated["policy_version_id"] = policy.policy_version_id
            applied_entries.append(updated)
            if after_amount != before_amount:
                affected_entries.append(
                    {
                        "intercompany_pair_id": row.get("intercompany_pair_id"),
                        "transaction_reference": row.get("transaction_reference"),
                        "before": str(before_amount),
                        "after": str(after_amount),
                        "adjustment": str(profit_adjustment),
                    }
                )
        if not affected_entries:
            warnings.append("NON_CRITICAL: no unrealized profit adjustments were required")
        return {
            "policy_applied_entries": applied_entries,
            "policy_version_id": policy.policy_version_id,
            "policy_effect": (
                str(policy.parameters.get("policy_effect", "adjustment"))
                if affected_entries
                else "none"
            ),
            "audit_trace": policy_audit_trace(
                policy=policy,
                rule_type="intercompany_profit_elimination",
                affected_entries=affected_entries,
                validation_report=validation["validation_report"],
                warnings=warnings,
                policy_source=policy_source,
                reason=source_reason,
            ),
        }

    def apply_minority_interest_policy(
        self,
        *,
        minority_interest_summary: dict[str, Any],
        current_date: date,
        policies: Iterable[Policy] | None = None,
    ) -> dict[str, Any]:
        policy, policy_source, source_reason = self._resolve_policy_entry(
            rule_type="minority_interest_adjustment",
            current_date=current_date,
            policies=policies,
        )
        entity_traces = list(minority_interest_summary.get("entity_traces") or [])
        validation = self._validation.validate_dataset(
            rules=minority_interest_policy_input_rules(),
            rows=entity_traces,
        )
        self._validation.raise_if_fail(report=validation)

        multiplier = self._decimal_param(policy, "adjustment_multiplier")
        basis = str(policy.parameters.get("basis", "partial_goodwill"))
        applied_entries: list[dict[str, Any]] = []
        affected_entries: list[dict[str, Any]] = []
        aggregate_amount = Decimal("0.000000")
        warnings: list[str] = []
        for row in self._sorted_dicts(
            entity_traces,
            keys=("entity_id", "source_metric_result_id", "metric_code"),
        ):
            before_amount = Decimal(str(row.get("minority_interest_value", "0")))
            after_amount = (before_amount * multiplier).quantize(Decimal("0.000000"))
            aggregate_amount += after_amount
            updated = dict(row)
            updated["minority_interest_value"] = str(after_amount)
            updated["policy_rule_type"] = "minority_interest_adjustment"
            updated["policy_basis"] = basis
            updated["policy_id"] = policy.policy_id
            updated["policy_version_id"] = policy.policy_version_id
            applied_entries.append(updated)
            if after_amount != before_amount:
                affected_entries.append(
                    {
                        "entity_id": row.get("entity_id"),
                        "source_metric_result_id": row.get("source_metric_result_id"),
                        "before": str(before_amount),
                        "after": str(after_amount),
                        "basis": basis,
                    }
                )
        if not affected_entries:
            warnings.append("NON_CRITICAL: minority-interest policy produced no valuation change")
        adjusted_summary = dict(minority_interest_summary)
        adjusted_summary["aggregate_amount"] = str(aggregate_amount.quantize(Decimal("0.000000")))
        adjusted_summary["entity_traces"] = applied_entries
        adjusted_summary["policy_application"] = {
            "policy_applied_entries": applied_entries,
            "policy_version_id": policy.policy_version_id,
            "policy_effect": (
                str(policy.parameters.get("policy_effect", "adjustment"))
                if affected_entries
                else "none"
            ),
            "audit_trace": policy_audit_trace(
                policy=policy,
                rule_type="minority_interest_adjustment",
                affected_entries=affected_entries,
                validation_report=validation["validation_report"],
                warnings=warnings,
                policy_source=policy_source,
                reason=source_reason,
            ),
        }
        return adjusted_summary

    def apply_revenue_reclassification_policy(
        self,
        *,
        consolidated_metrics: list[object],
        current_date: date,
        policies: Iterable[Policy] | None = None,
    ) -> dict[str, Any]:
        policy, policy_source, source_reason = self._resolve_policy_entry(
            rule_type="revenue_reclassification",
            current_date=current_date,
            policies=policies,
        )
        rows = [self._to_dict(row) for row in consolidated_metrics]
        validation = self._validation.validate_dataset(
            rules=revenue_policy_input_rules(),
            rows=rows,
        )
        self._validation.raise_if_fail(report=validation)

        rate = self._decimal_param(policy, "reclassification_rate")
        metric_codes = {
            str(value).strip().lower()
            for value in list(policy.parameters.get("metric_codes", []))
            if str(value).strip()
        }
        applied_entries: list[dict[str, Any]] = []
        affected_entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        for row in self._sorted_dicts(rows, keys=("metric_code", "currency_code")):
            before_amount = Decimal(str(row.get("aggregated_value", "0")))
            metric_code = str(row.get("metric_code", "")).strip().lower()
            is_revenue = metric_code in metric_codes
            adjustment = (
                before_amount.copy_abs() * rate if is_revenue else Decimal("0.000000")
            ).quantize(Decimal("0.000000"))
            signed_adjustment = adjustment if before_amount >= 0 else -adjustment
            after_amount = (
                before_amount - signed_adjustment if is_revenue else before_amount
            ).quantize(Decimal("0.000000"))
            updated = dict(row)
            updated["aggregated_value"] = str(after_amount)
            updated["policy_rule_type"] = "revenue_reclassification"
            updated["policy_adjustment_amount"] = str(adjustment)
            updated["policy_id"] = policy.policy_id
            updated["policy_version_id"] = policy.policy_version_id
            applied_entries.append(updated)
            if is_revenue and after_amount != before_amount:
                affected_entries.append(
                    {
                        "metric_code": row.get("metric_code"),
                        "currency_code": row.get("currency_code"),
                        "before": str(before_amount),
                        "after": str(after_amount),
                        "adjustment": str(adjustment),
                    }
                )
        if not affected_entries:
            warnings.append("NON_CRITICAL: no revenue entries required reclassification")
        return {
            "policy_applied_entries": applied_entries,
            "policy_version_id": policy.policy_version_id,
            "policy_effect": (
                str(policy.parameters.get("policy_effect", "adjustment"))
                if affected_entries
                else "none"
            ),
            "audit_trace": policy_audit_trace(
                policy=policy,
                rule_type="revenue_reclassification",
                affected_entries=affected_entries,
                validation_report=validation["validation_report"],
                warnings=warnings,
                policy_source=policy_source,
                reason=source_reason,
            ),
        }

    def _decimal_param(self, policy: Policy, key: str) -> Decimal:
        return Decimal(str(policy.parameters.get(key, "0.000000")))

    def _resolve_policy_entry(
        self,
        *,
        rule_type: PolicyRuleType,
        current_date: date,
        policies: Iterable[Policy] | None = None,
    ) -> tuple[Policy, str, str | None]:
        explicit_pool = tuple(policies) if policies is not None else self._policies
        explicit_candidates = self._eligible_candidates(
            pool=explicit_pool,
            rule_type=rule_type,
            current_date=current_date,
        )
        if explicit_candidates:
            return self._select_policy(explicit_candidates), "explicit", None

        if settings.REQUIRE_EXPLICIT_POLICY:
            raise ValueError(
                f"validation_report.status=FAIL: missing policy for rule_type {rule_type}"
            )

        default_candidates = self._eligible_candidates(
            pool=self._default_policies,
            rule_type=rule_type,
            current_date=current_date,
        )
        if not default_candidates:
            raise ValueError(
                f"validation_report.status=FAIL: missing policy for rule_type {rule_type}"
            )
        return (
            self._select_policy(default_candidates),
            "default",
            "no explicit policy configured",
        )

    def _eligible_candidates(
        self,
        *,
        pool: Iterable[Policy],
        rule_type: PolicyRuleType,
        current_date: date,
    ) -> list[Policy]:
        return [
            row
            for row in pool
            if row.rule_type == rule_type and row.effective_date <= current_date
        ]

    def _select_policy(self, candidates: list[Policy]) -> Policy:
        ordered = sorted(
            candidates,
            key=lambda row: (row.policy_version_id, row.effective_date, row.policy_id),
            reverse=True,
        )
        selected = ordered[0]
        ambiguous = [
            row
            for row in ordered
            if row.policy_version_id == selected.policy_version_id
            and row.effective_date == selected.effective_date
            and row.policy_id != selected.policy_id
        ]
        if ambiguous:
            raise ValueError(
                f"validation_report.status=FAIL: ambiguous policy selection for rule_type {selected.rule_type}"
            )
        return selected

    def _sorted_dicts(
        self, rows: list[dict[str, Any]], *, keys: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda row: tuple(str(row.get(key, "")) for key in keys))

    def _to_dict(self, row: object) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if is_dataclass(row):
            return asdict(row)
        if hasattr(row, "__dict__"):
            return {
                str(key): value
                for key, value in vars(row).items()
                if not str(key).startswith("_")
            }
        normalized: dict[str, Any] = {}
        for name in dir(row):
            if name.startswith("_"):
                continue
            value = getattr(row, name, None)
            if callable(value):
                continue
            normalized[name] = value
        return normalized
