from __future__ import annotations

from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
    MetricRunTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_metric_run_token(payload: MetricRunTokenInput, *, status: str) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "scope_json": payload.scope_json,
        "mis_snapshot_id": str(payload.mis_snapshot_id) if payload.mis_snapshot_id else None,
        "payroll_run_id": str(payload.payroll_run_id) if payload.payroll_run_id else None,
        "gl_run_id": str(payload.gl_run_id) if payload.gl_run_id else None,
        "reconciliation_session_id": (
            str(payload.reconciliation_session_id)
            if payload.reconciliation_session_id
            else None
        ),
        "payroll_gl_reconciliation_run_id": (
            str(payload.payroll_gl_reconciliation_run_id)
            if payload.payroll_gl_reconciliation_run_id
            else None
        ),
        "metric_definition_version_token": payload.metric_definition_version_token,
        "variance_definition_version_token": payload.variance_definition_version_token,
        "trend_definition_version_token": payload.trend_definition_version_token,
        "materiality_rule_version_token": payload.materiality_rule_version_token,
        "input_signature_hash": payload.input_signature_hash,
        "status": status,
    }
    return build_token(value)
