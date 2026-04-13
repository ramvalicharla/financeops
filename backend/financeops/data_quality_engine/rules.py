from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Literal

RuleSeverity = Literal["CRITICAL", "NON_CRITICAL"]


@dataclass(frozen=True)
class RowRule:
    name: str
    severity: RuleSeverity
    detail: str
    evaluator: Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class DatasetRule:
    name: str
    severity: RuleSeverity
    evaluator: Callable[[list[dict[str, Any]]], tuple[int, str] | None]


@dataclass(frozen=True)
class DatasetValidationRules:
    table: str
    required_columns: tuple[str, ...] = ()
    required_non_null: tuple[str, ...] = ()
    field_types: dict[str, tuple[type[Any], ...]] = field(default_factory=dict)
    numeric_fields: tuple[str, ...] = ()
    currency_fields: tuple[str, ...] = ()
    duplicate_key_fields: tuple[str, ...] = ()
    duplicate_severity: RuleSeverity = "NON_CRITICAL"
    row_rules: tuple[RowRule, ...] = ()
    dataset_rules: tuple[DatasetRule, ...] = ()


def trial_balance_balance_rule() -> RowRule:
    def _has_balance_mismatch(row: dict[str, Any]) -> bool:
        try:
            opening = Decimal(str(row.get("opening_balance", "0")))
            debit = Decimal(str(row.get("period_debit", "0")))
            credit = Decimal(str(row.get("period_credit", "0")))
            closing = Decimal(str(row.get("closing_balance", "0")))
        except Exception:
            return False
        return opening + debit - credit != closing

    return RowRule(
        name="numeric_consistency",
        severity="NON_CRITICAL",
        detail="Opening balance + debits - credits does not equal closing balance",
        evaluator=_has_balance_mismatch,
    )


def reconciliation_cross_account_rule(*, other_rows: list[dict[str, Any]], other_table: str) -> DatasetRule:
    other_accounts = {
        str(row.get("account_code", "")).strip()
        for row in other_rows
        if str(row.get("account_code", "")).strip()
    }

    def _evaluate(rows: list[dict[str, Any]]) -> tuple[int, str] | None:
        missing = sorted(
            {
                str(row.get("account_code", "")).strip()
                for row in rows
                if str(row.get("account_code", "")).strip()
                and str(row.get("account_code", "")).strip() not in other_accounts
            }
        )
        if not missing:
            return None
        sample = ", ".join(missing[:5])
        return (
            len(missing),
            f"Accounts missing corresponding rows in {other_table}: {sample}",
        )

    return DatasetRule(
        name="cross_table_consistency",
        severity="NON_CRITICAL",
        evaluator=_evaluate,
    )


def consolidation_metric_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="consolidation_source_metrics",
        required_columns=("id", "run_id", "metric_code", "metric_value"),
        required_non_null=("id", "run_id", "metric_code", "metric_value"),
        field_types={"metric_code": (str,)},
        numeric_fields=("metric_value",),
        currency_fields=("currency_code",),
        duplicate_key_fields=("run_id", "metric_code", "entity_id"),
    )


def consolidation_variance_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="consolidation_source_variances",
        required_columns=("id", "run_id", "metric_code", "comparison_type"),
        required_non_null=("id", "run_id", "metric_code", "comparison_type"),
        field_types={"metric_code": (str,), "comparison_type": (str,)},
        numeric_fields=("base_value", "current_value", "variance_value", "variance_pct"),
        currency_fields=("currency_code",),
        duplicate_key_fields=("run_id", "metric_code", "comparison_type"),
    )


def reconciliation_gl_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="gl_entries",
        required_columns=(
            "account_code",
            "account_name",
            "entity_name",
            "debit_amount",
            "credit_amount",
            "currency",
        ),
        required_non_null=(
            "account_code",
            "account_name",
            "entity_name",
            "debit_amount",
            "credit_amount",
            "currency",
        ),
        field_types={
            "account_code": (str,),
            "account_name": (str,),
            "entity_name": (str,),
            "currency": (str,),
        },
        numeric_fields=("debit_amount", "credit_amount"),
        currency_fields=("currency",),
        duplicate_key_fields=("account_code", "entity_name", "source_ref"),
    )


def reconciliation_tb_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="trial_balance_rows",
        required_columns=(
            "account_code",
            "account_name",
            "entity_name",
            "opening_balance",
            "period_debit",
            "period_credit",
            "closing_balance",
            "currency",
        ),
        required_non_null=(
            "account_code",
            "account_name",
            "entity_name",
            "opening_balance",
            "period_debit",
            "period_credit",
            "closing_balance",
            "currency",
        ),
        field_types={
            "account_code": (str,),
            "account_name": (str,),
            "entity_name": (str,),
            "currency": (str,),
        },
        numeric_fields=("opening_balance", "period_debit", "period_credit", "closing_balance"),
        currency_fields=("currency",),
        duplicate_key_fields=("account_code", "entity_name"),
        row_rules=(trial_balance_balance_rule(),),
    )


def report_source_rules(*, table_name: str, value_column: str) -> DatasetValidationRules:
    return DatasetValidationRules(
        table=table_name,
        required_columns=(value_column,),
        required_non_null=(value_column,),
        numeric_fields=(value_column,),
        currency_fields=("currency_code",),
        duplicate_key_fields=("reporting_period", "metric_value"),
        duplicate_severity="NON_CRITICAL",
    )


def reconciliation_balance_source_rules(*, table_name: str) -> DatasetValidationRules:
    return DatasetValidationRules(
        table=table_name,
        required_columns=("account", "entity", "currency", "period", "value"),
        required_non_null=("account", "entity", "currency", "period", "value"),
        field_types={
            "account": (str,),
            "entity": (str,),
            "currency": (str,),
            "period": (str,),
        },
        numeric_fields=("value",),
        currency_fields=("currency",),
        duplicate_key_fields=("account", "entity", "currency", "period"),
    )


def ageing_line_rules(*, table_name: str, party_field: str) -> DatasetValidationRules:
    return DatasetValidationRules(
        table=table_name,
        required_columns=("snapshot_id", party_field, "days_overdue", "amount_base_currency", "currency"),
        required_non_null=("snapshot_id", party_field, "days_overdue", "amount_base_currency", "currency"),
        field_types={
            party_field: (str,),
            "currency": (str,),
        },
        numeric_fields=("days_overdue", "amount_base_currency"),
        currency_fields=("currency",),
        duplicate_key_fields=("snapshot_id", "invoice_number", party_field),
    )


def inventory_snapshot_rules() -> DatasetValidationRules:
    return DatasetValidationRules(
        table="working_capital_snapshots",
        required_columns=("period_year", "period_month", "entity_name", "inventory", "currency"),
        required_non_null=("period_year", "period_month", "entity_name", "inventory", "currency"),
        field_types={
            "entity_name": (str,),
            "currency": (str,),
        },
        numeric_fields=("inventory",),
        currency_fields=("currency",),
        duplicate_key_fields=("period_year", "period_month", "entity_name"),
    )
