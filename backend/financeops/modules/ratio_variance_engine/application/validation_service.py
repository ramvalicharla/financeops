from __future__ import annotations

from datetime import date
from typing import Any

from financeops.db.models.mis_manager import MisDataSnapshot
from financeops.db.models.payroll_gl_normalization import NormalizationRun
from financeops.db.models.payroll_gl_reconciliation import PayrollGlReconciliationRun
from financeops.db.models.reconciliation_bridge import ReconciliationSession


class ValidationService:
    def validate_definition_sets(
        self,
        *,
        metric_definitions: list[Any],
        variance_definitions: list[Any],
        trend_definitions: list[Any],
        materiality_rules: list[Any],
    ) -> None:
        if not metric_definitions:
            raise ValueError("No active metric definitions found")
        if not variance_definitions:
            raise ValueError("No active variance definitions found")
        if not trend_definitions:
            raise ValueError("No active trend definitions found")
        if not materiality_rules:
            raise ValueError("No active materiality rules found")

    def validate_sources(
        self,
        *,
        reporting_period: date,
        mis_snapshot: MisDataSnapshot | None,
        payroll_run: NormalizationRun | None,
        gl_run: NormalizationRun | None,
        reconciliation_session: ReconciliationSession | None,
        payroll_gl_reconciliation_run: PayrollGlReconciliationRun | None,
    ) -> None:
        if (
            mis_snapshot is None
            and payroll_run is None
            and gl_run is None
            and reconciliation_session is None
            and payroll_gl_reconciliation_run is None
        ):
            raise ValueError("At least one normalized or reconciliation input is required")

        if mis_snapshot is not None:
            if mis_snapshot.snapshot_status not in {"validated", "finalized"}:
                raise ValueError("MIS snapshot must be validated/finalized")
            if mis_snapshot.reporting_period != reporting_period:
                raise ValueError("MIS snapshot reporting period mismatch")

        if payroll_run is not None:
            if payroll_run.run_type != "payroll_normalization":
                raise ValueError("payroll_run_id must reference payroll_normalization run")
            if payroll_run.run_status != "finalized":
                raise ValueError("Payroll normalization run must be finalized")
            if payroll_run.reporting_period != reporting_period:
                raise ValueError("Payroll normalization reporting period mismatch")

        if gl_run is not None:
            if gl_run.run_type != "gl_normalization":
                raise ValueError("gl_run_id must reference gl_normalization run")
            if gl_run.run_status != "finalized":
                raise ValueError("GL normalization run must be finalized")
            if gl_run.reporting_period != reporting_period:
                raise ValueError("GL normalization reporting period mismatch")

        if reconciliation_session is not None:
            if reconciliation_session.status != "completed":
                raise ValueError("Reconciliation session must be completed")
            if reconciliation_session.period_end != reporting_period:
                raise ValueError("Reconciliation session reporting period mismatch")

        if payroll_gl_reconciliation_run is not None:
            if payroll_gl_reconciliation_run.status != "completed":
                raise ValueError("Payroll-GL reconciliation run must be completed")
            if payroll_gl_reconciliation_run.reporting_period != reporting_period:
                raise ValueError("Payroll-GL reconciliation run reporting period mismatch")

    def validate_scope(self, *, scope_json: dict[str, Any]) -> None:
        if not isinstance(scope_json, dict):
            raise ValueError("scope_json must be an object")
