from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from financeops.accounting_policy_engine.models import Policy
from financeops.data_quality_engine.rules import DatasetValidationRules


def default_policies() -> tuple[Policy, ...]:
    return (
        Policy(
            policy_id="policy.ic_profit.default",
            policy_version_id=1,
            effective_date=date(2000, 1, 1),
            rule_type="intercompany_profit_elimination",
            parameters={
                "severity": "CRITICAL",
                "unrealized_profit_rate": Decimal("0.000000"),
                "policy_effect": "adjustment",
            },
        ),
        Policy(
            policy_id="policy.minority_interest.default",
            policy_version_id=1,
            effective_date=date(2000, 1, 1),
            rule_type="minority_interest_adjustment",
            parameters={
                "severity": "CRITICAL",
                "basis": "partial_goodwill",
                "adjustment_multiplier": Decimal("1.000000"),
                "policy_effect": "adjustment",
            },
        ),
        Policy(
            policy_id="policy.revenue_reclassification.default",
            policy_version_id=1,
            effective_date=date(2000, 1, 1),
            rule_type="revenue_reclassification",
            parameters={
                "severity": "CRITICAL",
                "metric_codes": ["revenue", "net_revenue", "ic_sales"],
                "reclassification_rate": Decimal("0.000000"),
                "policy_effect": "adjustment",
            },
        ),
    )


def intercompany_policy_input_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="policy_intercompany_elimination_entries",
        required_columns=(
            "intercompany_pair_id",
            "entity_from",
            "entity_to",
            "account_code",
            "eliminated_amount_parent",
            "transaction_reference",
        ),
        required_non_null=(
            "intercompany_pair_id",
            "entity_from",
            "entity_to",
            "account_code",
            "eliminated_amount_parent",
            "transaction_reference",
        ),
        field_types={
            "entity_from": (str,),
            "entity_to": (str,),
            "account_code": (str,),
            "transaction_reference": (str,),
        },
        numeric_fields=("eliminated_amount_parent",),
        duplicate_key_fields=("intercompany_pair_id", "transaction_reference"),
        duplicate_severity="NON_CRITICAL",
    )


def minority_interest_policy_input_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="policy_minority_interest_traces",
        required_columns=(
            "entity_id",
            "source_metric_result_id",
            "source_balance",
            "ownership_percentage",
            "minority_interest_value",
        ),
        required_non_null=(
            "entity_id",
            "source_metric_result_id",
            "source_balance",
            "ownership_percentage",
            "minority_interest_value",
        ),
        field_types={
            "entity_id": (str,),
            "source_metric_result_id": (str,),
            "metric_code": (str,),
        },
        numeric_fields=("source_balance", "ownership_percentage", "minority_interest_value"),
        duplicate_key_fields=("entity_id", "source_metric_result_id"),
        duplicate_severity="NON_CRITICAL",
    )


def revenue_policy_input_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="policy_consolidated_revenue_entries",
        required_columns=("metric_code", "aggregated_value", "currency_code", "entity_count"),
        required_non_null=("metric_code", "aggregated_value", "currency_code", "entity_count"),
        field_types={
            "metric_code": (str,),
            "currency_code": (str,),
        },
        numeric_fields=("aggregated_value", "entity_count"),
        currency_fields=("currency_code",),
        duplicate_key_fields=("metric_code", "currency_code"),
        duplicate_severity="NON_CRITICAL",
    )


def policy_audit_trace(
    *,
    policy: Policy,
    rule_type: str,
    affected_entries: list[dict[str, Any]],
    validation_report: dict[str, Any],
    warnings: list[str] | None = None,
    policy_source: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    trace = {
        "policy_id": policy.policy_id,
        "policy_version_id": policy.policy_version_id,
        "rule_type": rule_type,
        "affected_entries": affected_entries,
        "validation_report": validation_report,
        "warnings": list(warnings or []),
    }
    if policy_source is not None:
        trace["policy_source"] = policy_source
    if reason is not None:
        trace["reason"] = reason
    return trace
