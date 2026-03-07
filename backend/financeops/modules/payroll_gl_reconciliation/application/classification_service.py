from __future__ import annotations

from financeops.modules.payroll_gl_reconciliation.domain.entities import (
    PayrollGlComparisonLine,
    PayrollGlComputedException,
)
from financeops.modules.payroll_gl_reconciliation.domain.enums import CoreDifferenceType


class ClassificationService:
    def classify_line(
        self, line: PayrollGlComparisonLine
    ) -> PayrollGlComputedException | None:
        if line.core_difference_type == CoreDifferenceType.NONE:
            return None
        severity = "error" if line.materiality_flag else "warning"
        return PayrollGlComputedException(
            line_key=line.line_key,
            exception_code=f"PAYROLL_GL_{line.payroll_difference_type.value.upper()}",
            severity=severity,
            message=(
                "Payroll-GL mismatch detected: "
                f"{line.payroll_difference_type.value} (variance={line.variance_value})"
            ),
            owner_role="finance_controller",
        )

