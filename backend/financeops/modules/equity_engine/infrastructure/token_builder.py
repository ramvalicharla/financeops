from __future__ import annotations

from financeops.modules.equity_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
    EquityRunTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_equity_run_token(payload: EquityRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "statement_definition_version_token": payload.statement_definition_version_token,
        "line_definition_version_token": payload.line_definition_version_token,
        "rollforward_rule_version_token": payload.rollforward_rule_version_token,
        "source_mapping_version_token": payload.source_mapping_version_token,
        "consolidation_run_ref_nullable": payload.consolidation_run_ref_nullable,
        "fx_translation_run_ref_nullable": payload.fx_translation_run_ref_nullable,
        "ownership_consolidation_run_ref_nullable": payload.ownership_consolidation_run_ref_nullable,
        "run_status": payload.run_status,
    }
    return build_token(value)
