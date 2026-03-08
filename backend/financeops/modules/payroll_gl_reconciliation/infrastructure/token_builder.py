from __future__ import annotations

from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    MappingVersionTokenInput,
    PayrollGlRunTokenInput,
    RuleVersionTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_mapping_version_token(payload: MappingVersionTokenInput) -> str:
    return build_version_rows_token(payload.mapping_rows)


def build_rule_version_token(payload: RuleVersionTokenInput) -> str:
    return build_version_rows_token(payload.rule_rows)


def build_payroll_gl_run_token(payload: PayrollGlRunTokenInput, *, status: str) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "payroll_run_id": str(payload.payroll_run_id),
        "gl_run_id": str(payload.gl_run_id),
        "mapping_version_token": payload.mapping_version_token,
        "rule_version_token": payload.rule_version_token,
        "reporting_period": payload.reporting_period.isoformat(),
        "status": status,
    }
    return build_token(value)
