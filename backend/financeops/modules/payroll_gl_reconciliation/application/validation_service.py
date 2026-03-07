from __future__ import annotations

from datetime import date

from financeops.db.models.payroll_gl_normalization import NormalizationRun
from financeops.db.models.payroll_gl_reconciliation import (
    PayrollGlReconciliationMapping,
    PayrollGlReconciliationRule,
)
from financeops.modules.payroll_gl_normalization.domain.enums import RunStatus


class ValidationService:
    REQUIRED_PAYROLL_METRIC_ANCHORS: tuple[str, ...] = ("gross_pay", "net_pay")

    def validate_run_inputs(
        self,
        *,
        payroll_run: NormalizationRun | None,
        gl_run: NormalizationRun | None,
        organisation_id: str,
        reporting_period: date,
        mappings: list[PayrollGlReconciliationMapping],
        rules: list[PayrollGlReconciliationRule],
    ) -> None:
        if payroll_run is None:
            raise ValueError("Payroll normalization run not found")
        if gl_run is None:
            raise ValueError("GL normalization run not found")
        if payroll_run.run_type != "payroll_normalization":
            raise ValueError("payroll_run_id must reference payroll_normalization run")
        if gl_run.run_type != "gl_normalization":
            raise ValueError("gl_run_id must reference gl_normalization run")
        if payroll_run.run_status != RunStatus.FINALIZED.value:
            raise ValueError("Payroll normalization run must be finalized")
        if gl_run.run_status != RunStatus.FINALIZED.value:
            raise ValueError("GL normalization run must be finalized")
        if str(payroll_run.organisation_id) != organisation_id:
            raise ValueError("payroll_run_id organisation does not match")
        if str(gl_run.organisation_id) != organisation_id:
            raise ValueError("gl_run_id organisation does not match")
        if payroll_run.reporting_period != reporting_period:
            raise ValueError("payroll_run_id reporting period mismatch")
        if gl_run.reporting_period != reporting_period:
            raise ValueError("gl_run_id reporting period mismatch")
        if not mappings:
            raise ValueError("No active mapping set found for reporting period")
        if not rules:
            raise ValueError("No active rule set found for reporting period")

        mapped_metrics = {row.payroll_metric_code for row in mappings}
        missing = sorted(
            metric
            for metric in self.REQUIRED_PAYROLL_METRIC_ANCHORS
            if metric not in mapped_metrics
        )
        if missing:
            raise ValueError(
                "Required payroll metrics not mapped: " + ", ".join(missing)
            )

