from __future__ import annotations

from collections import Counter
from typing import Any

from financeops.modules.payroll_gl_normalization.domain.entities import (
    GlNormalizedEntry,
    NormalizationExceptionEntry,
    PayrollNormalizedEntry,
)
from financeops.modules.payroll_gl_normalization.domain.enums import ExceptionSeverity


class ValidationService:
    def validate_upload_shape(
        self, *, run_type: str, headers: list[str]
    ) -> list[NormalizationExceptionEntry]:
        normalized = {str(item).strip().lower() for item in headers if str(item).strip()}
        exceptions: list[NormalizationExceptionEntry] = []
        if run_type == "payroll_normalization":
            if not any("employee" in header for header in normalized):
                exceptions.append(
                    NormalizationExceptionEntry(
                        exception_code="REQUIRED_FIELD_MISSING",
                        severity=ExceptionSeverity.ERROR,
                        source_ref="headers",
                        message="Payroll upload requires employee anchor column",
                    )
                )
        else:
            if not any("account" in header for header in normalized):
                exceptions.append(
                    NormalizationExceptionEntry(
                        exception_code="REQUIRED_FIELD_MISSING",
                        severity=ExceptionSeverity.ERROR,
                        source_ref="headers",
                        message="GL upload requires account anchor column",
                    )
                )
        return exceptions

    def validate_payroll_lines(
        self, *, lines: list[PayrollNormalizedEntry]
    ) -> list[NormalizationExceptionEntry]:
        exceptions: list[NormalizationExceptionEntry] = []
        seen = Counter(
            (
                line.employee_code or line.employee_name or "unknown",
                line.payroll_period.isoformat(),
                line.canonical_metric_code,
            )
            for line in lines
        )
        for key, count in seen.items():
            if count <= 1:
                continue
            exceptions.append(
                NormalizationExceptionEntry(
                    exception_code="DUPLICATE_EMPLOYEE_PERIOD",
                    severity=ExceptionSeverity.WARNING,
                    source_ref=f"employee_period_metric:{key}",
                    message="Duplicate employee + period + metric combination detected",
                )
            )
        return exceptions

    def validate_gl_lines(
        self, *, lines: list[GlNormalizedEntry]
    ) -> list[NormalizationExceptionEntry]:
        exceptions: list[NormalizationExceptionEntry] = []
        duplicates = Counter(
            (line.journal_id or "none", line.journal_line_no or "none") for line in lines
        )
        for key, count in duplicates.items():
            if key == ("none", "none") or count <= 1:
                continue
            exceptions.append(
                NormalizationExceptionEntry(
                    exception_code="DUPLICATE_JOURNAL_LINE",
                    severity=ExceptionSeverity.WARNING,
                    source_ref=f"journal_line:{key}",
                    message="Duplicate journal + line combination detected",
                )
            )
        return exceptions

    def summarize(self, *, exceptions: list[NormalizationExceptionEntry]) -> dict[str, Any]:
        severities = Counter(item.severity.value for item in exceptions)
        status = "validated"
        if severities.get("error", 0) > 0:
            status = "failed"
        return {
            "status": status,
            "error_count": int(severities.get("error", 0)),
            "warning_count": int(severities.get("warning", 0)),
            "info_count": int(severities.get("info", 0)),
        }
