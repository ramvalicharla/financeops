from __future__ import annotations

from financeops.modules.cash_flow_engine.domain.value_objects import (
    CashFlowRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_cash_flow_run_token(payload: CashFlowRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "statement_definition_version_token": payload.statement_definition_version_token,
        "line_mapping_version_token": payload.line_mapping_version_token,
        "bridge_rule_version_token": payload.bridge_rule_version_token,
        "source_consolidation_run_ref": payload.source_consolidation_run_ref,
        "source_fx_translation_run_ref_nullable": payload.source_fx_translation_run_ref_nullable,
        "source_ownership_consolidation_run_ref_nullable": payload.source_ownership_consolidation_run_ref_nullable,
        "run_status": payload.run_status,
    }
    return build_token(value)
