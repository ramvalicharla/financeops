from __future__ import annotations

from financeops.modules.multi_entity_consolidation.domain.value_objects import (
    ConsolidationRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_consolidation_run_token(payload: ConsolidationRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "hierarchy_version_token": payload.hierarchy_version_token,
        "scope_version_token": payload.scope_version_token,
        "rule_version_token": payload.rule_version_token,
        "intercompany_version_token": payload.intercompany_version_token,
        "adjustment_version_token": payload.adjustment_version_token,
        "source_run_refs": payload.source_run_refs,
        "run_status": payload.run_status,
    }
    return build_token(value)

