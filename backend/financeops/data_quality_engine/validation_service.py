from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from financeops.data_quality_engine.rules import (
    DatasetRule,
    DatasetValidationRules,
    RowRule,
)


class DataQualityValidationError(ValueError):
    def __init__(self, validation_report: dict[str, Any]) -> None:
        super().__init__("validation_report.status=FAIL")
        self.validation_report = validation_report


class DataQualityValidationService:
    def validate_dataset(
        self,
        *,
        rules: DatasetValidationRules,
        rows: list[object] | list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_rows = [self._normalize_row(row) for row in rows]
        if not normalized_rows:
            return {
                "validation_report": {
                    "table": rules.table,
                    "status": "PASS",
                    "failures": [],
                    "warnings": [],
                    "summary": {
                        "total_rows_checked": 0,
                        "failed_rows": 0,
                        "failed_checks": 0,
                    },
                }
            }
        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        total_rows = len(normalized_rows)
        available_columns = set().union(*(row.keys() for row in normalized_rows)) if normalized_rows else set()
        failed_row_indexes: set[int] = set()
        failed_checks = 0

        for column in rules.required_columns:
            if column not in available_columns:
                issue = {
                    "column": column,
                    "rule": "required_column",
                    "row_count": total_rows,
                }
                failures.append(issue)
                failed_row_indexes.update(range(total_rows))
                failed_checks += total_rows

        for column in rules.required_non_null:
            failing_rows = {
                index
                for index, row in enumerate(normalized_rows)
                if self._is_empty(row.get(column))
            }
            if failing_rows:
                issue = {
                    "column": column,
                    "rule": "not_null",
                    "row_count": len(failing_rows),
                }
                failures.append(issue)
                failed_row_indexes.update(failing_rows)
                failed_checks += len(failing_rows)

        for column, expected_types in rules.field_types.items():
            invalid_rows = {
                index
                for index, row in enumerate(normalized_rows)
                if not self._is_empty(row.get(column))
                and not isinstance(row.get(column), expected_types)
            }
            if invalid_rows:
                warnings.append(
                    {
                        "column": column,
                        "rule": "type_mismatch",
                        "row_count": len(invalid_rows),
                    }
                )

        for column in rules.numeric_fields:
            invalid_rows = {
                index
                for index, row in enumerate(normalized_rows)
                if not self._is_empty(row.get(column)) and not self._is_decimal_like(row.get(column))
            }
            if invalid_rows:
                warnings.append(
                    {
                        "column": column,
                        "rule": "numeric_consistency",
                        "row_count": len(invalid_rows),
                    }
                )

        for column in rules.currency_fields:
            invalid_rows = {
                index
                for index, row in enumerate(normalized_rows)
                if not self._is_empty(row.get(column)) and not self._is_currency_code(row.get(column))
            }
            if invalid_rows:
                warnings.append(
                    {
                        "column": column,
                        "rule": "type_mismatch",
                        "row_count": len(invalid_rows),
                    }
                )
            distinct = sorted(
                {
                    str(row.get(column, "")).strip().upper()
                    for row in normalized_rows
                    if not self._is_empty(row.get(column))
                }
            )
            if len(distinct) > 1:
                warnings.append(
                    {
                        "column": column,
                        "rule": "currency_consistency",
                        "row_count": len(
                            [row for row in normalized_rows if not self._is_empty(row.get(column))]
                        ),
                        "detail": f"Multiple currencies present: {', '.join(distinct)}",
                    }
                )

        if rules.duplicate_key_fields:
            duplicate_count = self._duplicate_count(normalized_rows, rules.duplicate_key_fields)
            if duplicate_count > 0:
                issue = {
                    "rule": "duplicate_rows",
                    "detail": f"Duplicate rows detected for key set {', '.join(rules.duplicate_key_fields)}",
                    "row_count": duplicate_count,
                }
                if rules.duplicate_severity == "CRITICAL":
                    failures.append(issue)
                    failed_row_indexes.update(range(min(total_rows, duplicate_count + 1)))
                    failed_checks += duplicate_count
                else:
                    warnings.append(issue)

        for row_rule in rules.row_rules:
            matching_indexes = {
                index for index, row in enumerate(normalized_rows) if row_rule.evaluator(row)
            }
            if matching_indexes:
                added_failure_checks = self._append_issue(
                    bucket_failures=failures,
                    bucket_warnings=warnings,
                    severity=row_rule.severity,
                    failure_indexes=failed_row_indexes,
                    issue={
                        "rule": row_rule.name,
                        "detail": row_rule.detail,
                        "row_count": len(matching_indexes),
                    },
                    row_indexes=matching_indexes,
                )
                failed_checks += added_failure_checks

        for dataset_rule in rules.dataset_rules:
            outcome = dataset_rule.evaluator(normalized_rows)
            if outcome is None:
                continue
            row_count, detail = outcome
            affected_rows = set(range(min(total_rows, max(row_count, 0))))
            added_failure_checks = self._append_issue(
                bucket_failures=failures,
                bucket_warnings=warnings,
                severity=dataset_rule.severity,
                failure_indexes=failed_row_indexes,
                issue={
                    "rule": dataset_rule.name,
                    "detail": detail,
                    "row_count": row_count,
                },
                row_indexes=affected_rows,
            )
            failed_checks += added_failure_checks

        status = "FAIL" if failures else "WARN" if warnings else "PASS"
        validation_report = {
            "table": rules.table,
            "status": status,
            "failures": failures,
            "warnings": warnings,
            "summary": {
                "total_rows_checked": total_rows,
                "failed_rows": len(failed_row_indexes),
                "failed_checks": failed_checks,
            },
        }
        return {"validation_report": validation_report}

    def raise_if_fail(self, *, report: dict[str, Any]) -> None:
        validation_report = report["validation_report"]
        if validation_report["status"] == "FAIL":
            raise DataQualityValidationError(validation_report)

    def _append_issue(
        self,
        *,
        bucket_failures: list[dict[str, Any]],
        bucket_warnings: list[dict[str, Any]],
        severity: str,
        failure_indexes: set[int],
        issue: dict[str, Any],
        row_indexes: set[int],
    ) -> int:
        if severity == "CRITICAL":
            bucket_failures.append(issue)
            failure_indexes.update(row_indexes)
            return int(issue.get("row_count", 0) or 0)
        bucket_warnings.append(issue)
        return 0

    def _normalize_row(self, row: object | dict[str, Any]) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
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

    def _is_empty(self, value: Any) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    def _is_decimal_like(self, value: Any) -> bool:
        try:
            Decimal(str(value))
            return True
        except (InvalidOperation, TypeError, ValueError):
            return False

    def _is_currency_code(self, value: Any) -> bool:
        text = str(value).strip().upper()
        return len(text) == 3 and text.isalpha()

    def _duplicate_count(self, rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> int:
        seen: set[tuple[str, ...]] = set()
        duplicates = 0
        for row in rows:
            key = tuple(str(row.get(field, "")).strip() for field in key_fields)
            if not any(part for part in key):
                continue
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
        return duplicates
