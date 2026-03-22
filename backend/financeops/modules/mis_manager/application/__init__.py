from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.mis_manager.domain.entities import (
    NormalizedLine,
    ValidationException,
)
from financeops.modules.mis_manager.domain.enums import ValidationStatus


class ValidationService:
    def validate_snapshot(
        self,
        *,
        template_type: str,
        headers: list[str],
        lines: list[NormalizedLine],
        currency_codes: list[str],
    ) -> tuple[list[ValidationException], dict[str, Any]]:
        exceptions: list[ValidationException] = []

        if not _has_period_column(headers):
            exceptions.append(
                ValidationException(
                    exception_code="PERIOD_COLUMN_NOT_FOUND",
                    severity="error",
                    source_ref="header",
                    message="No reporting period column detected",
                )
            )

        numeric_line_count = sum(
            1
            for line in lines
            if line.validation_status
            in {ValidationStatus.VALID, ValidationStatus.WARNING}
        )
        if numeric_line_count == 0:
            exceptions.append(
                ValidationException(
                    exception_code="NO_NUMERIC_BLOCK",
                    severity="error",
                    source_ref="lines",
                    message="At least one measurable numeric block is required",
                )
            )

        if template_type == "pnl_monthly":
            metrics = {line.canonical_metric_code for line in lines}
            has_revenue = "revenue_net" in metrics or "revenue_gross" in metrics
            has_expense = any(
                metric.endswith("_expense") or metric.startswith("cogs_")
                for metric in metrics
            )
            if not has_revenue or not has_expense:
                exceptions.append(
                    ValidationException(
                        exception_code="MISSING_REQUIRED_ROW",
                        severity="error",
                        source_ref="line_metrics",
                        message="P&L templates require revenue and expense anchors",
                    )
                )

        duplicate_keys = _find_duplicate_metric_dimension(lines)
        for dup in duplicate_keys:
            exceptions.append(
                ValidationException(
                    exception_code="DUPLICATE_METRIC_DIMENSION",
                    severity="error",
                    source_ref=dup,
                    message="Duplicate metric+dimension grain detected",
                )
            )

        unique_currencies = sorted({code for code in currency_codes if code})
        if len(unique_currencies) > 1:
            exceptions.append(
                ValidationException(
                    exception_code="MIXED_CURRENCY",
                    severity="warning",
                    source_ref="currency",
                    message="Mixed currency detected in a single snapshot",
                )
            )

        severity_counts = {
            "error": sum(1 for item in exceptions if item.severity == "error"),
            "warning": sum(1 for item in exceptions if item.severity == "warning"),
            "info": sum(1 for item in exceptions if item.severity == "info"),
        }
        summary = {
            "rule_set": "mis_validation_v1",
            "numeric_line_count": numeric_line_count,
            "exception_counts": severity_counts,
            "status": "failed" if severity_counts["error"] > 0 else "passed",
            "total_value": str(
                sum((line.period_value for line in lines), start=Decimal("0"))
            ),
        }
        return exceptions, summary


def _has_period_column(headers: list[str]) -> bool:
    tokens = ("period", "month", "year", "fy", "q1", "q2", "q3", "q4")
    normalized_headers = [header.strip().lower() for header in headers]
    return any(
        any(token in header for token in tokens) for header in normalized_headers
    )


def _find_duplicate_metric_dimension(lines: list[NormalizedLine]) -> list[str]:
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for line in lines:
        key = f"{line.canonical_metric_code}:{line.canonical_dimension_json}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicates.append(key)
    return duplicates
