from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from financeops.data_quality_engine import (
    DataQualityValidationError,
    DataQualityValidationService,
    DatasetValidationRules,
)


def test_valid_dataset_returns_pass() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="gl_entries",
            required_columns=("account_code", "debit_amount"),
            required_non_null=("account_code", "debit_amount"),
            numeric_fields=("debit_amount",),
        ),
        rows=[
            {"account_code": "1000", "debit_amount": Decimal("10.00")},
            {"account_code": "2000", "debit_amount": Decimal("0.00")},
        ],
    )

    assert report["validation_report"]["status"] == "PASS"
    assert report["validation_report"]["failures"] == []
    assert report["validation_report"]["warnings"] == []
    assert report["validation_report"]["summary"]["failed_rows"] == 0
    assert report["validation_report"]["summary"]["failed_checks"] == 0


def test_minor_issues_return_warn() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="gl_entries",
            required_columns=("account_code", "currency"),
            required_non_null=("account_code", "currency"),
            currency_fields=("currency",),
            duplicate_key_fields=("account_code",),
        ),
        rows=[
            {"account_code": "1000", "currency": "USD"},
            {"account_code": "1000", "currency": "INR"},
        ],
    )

    assert report["validation_report"]["status"] == "WARN"
    assert report["validation_report"]["failures"] == []
    assert len(report["validation_report"]["warnings"]) >= 2
    assert {warning["rule"] for warning in report["validation_report"]["warnings"]} >= {
        "currency_consistency",
        "duplicate_rows",
    }


def test_missing_required_column_returns_fail() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="trial_balance_rows",
            required_columns=("account_code", "closing_balance"),
            required_non_null=("account_code", "closing_balance"),
        ),
        rows=[{"account_code": "1000"}],
    )

    assert report["validation_report"]["status"] == "FAIL"
    assert report["validation_report"]["failures"][0]["rule"] == "required_column"
    assert report["validation_report"]["summary"]["failed_rows"] == 1
    assert report["validation_report"]["summary"]["failed_checks"] == 2
    with pytest.raises(DataQualityValidationError, match="validation_report.status=FAIL"):
        service.raise_if_fail(report=report)


def test_null_violation_returns_fail() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="consolidation_source_metrics",
            required_columns=("metric_code", "metric_value"),
            required_non_null=("metric_code", "metric_value"),
        ),
        rows=[
            {"metric_code": "revenue", "metric_value": Decimal("100.00")},
            {"metric_code": None, "metric_value": Decimal("50.00")},
        ],
    )

    assert report["validation_report"]["status"] == "FAIL"
    assert any(item["rule"] == "not_null" for item in report["validation_report"]["failures"])
    assert report["validation_report"]["summary"]["failed_rows"] == 1
    assert report["validation_report"]["summary"]["failed_checks"] == 1


def test_duplicate_rows_warn_by_default() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="report_rows",
            duplicate_key_fields=("metric_key", "reporting_period"),
        ),
        rows=[
            {"metric_key": "mis.kpi.revenue", "reporting_period": "2026-01-31"},
            {"metric_key": "mis.kpi.revenue", "reporting_period": "2026-01-31"},
        ],
    )

    assert report["validation_report"]["status"] == "WARN"
    assert report["validation_report"]["warnings"][0]["rule"] == "duplicate_rows"


def test_failed_rows_and_failed_checks_are_separate() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="trial_balance_rows",
            required_columns=("account_code", "closing_balance"),
            required_non_null=("account_code", "closing_balance"),
        ),
        rows=[
            {"account_code": None, "closing_balance": None},
            {"account_code": "2000", "closing_balance": None},
        ],
    )

    assert report["validation_report"]["status"] == "FAIL"
    assert report["validation_report"]["summary"]["failed_rows"] == 2
    assert report["validation_report"]["summary"]["failed_checks"] == 3


def test_type_mismatch_uses_standard_rule_name() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="gl_entries",
            field_types={"account_code": (str,)},
        ),
        rows=[{"account_code": 1000}],
    )

    assert report["validation_report"]["status"] == "WARN"
    assert report["validation_report"]["warnings"][0]["rule"] == "type_mismatch"


def test_object_rows_are_normalized() -> None:
    service = DataQualityValidationService()
    report = service.validate_dataset(
        rules=DatasetValidationRules(
            table="object_rows",
            required_columns=("account_code", "debit_amount"),
            required_non_null=("account_code", "debit_amount"),
            numeric_fields=("debit_amount",),
        ),
        rows=[SimpleNamespace(account_code="1000", debit_amount=Decimal("10.00"))],
    )

    assert report["validation_report"]["status"] == "PASS"
