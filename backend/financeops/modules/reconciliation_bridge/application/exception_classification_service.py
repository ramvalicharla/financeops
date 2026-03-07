from __future__ import annotations

from financeops.modules.reconciliation_bridge.domain.entities import (
    ReconciliationComputedException,
    ReconciliationComputedLine,
)
from financeops.modules.reconciliation_bridge.domain.enums import ExceptionSeverity


class ExceptionClassificationService:
    def classify(self, line: ReconciliationComputedLine) -> ReconciliationComputedException | None:
        if line.reconciliation_status.value != "exception":
            return None

        code = f"RECON_{line.difference_type.value.upper()}"
        severity = ExceptionSeverity.ERROR if line.materiality_flag else ExceptionSeverity.WARNING
        message = (
            f"Reconciliation difference detected: {line.difference_type.value} "
            f"(variance={line.variance_value})"
        )
        return ReconciliationComputedException(
            line_key=line.line_key,
            exception_code=code,
            severity=severity,
            message=message,
            owner_role="finance_controller",
        )
