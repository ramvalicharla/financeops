from __future__ import annotations

from financeops.modules.ownership_consolidation.domain.value_objects import (
    DefinitionVersionTokenInput,
    OwnershipRunTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_ownership_run_token(payload: OwnershipRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "hierarchy_version_token": payload.hierarchy_version_token,
        "scope_version_token": payload.scope_version_token,
        "ownership_structure_version_token": payload.ownership_structure_version_token,
        "ownership_rule_version_token": payload.ownership_rule_version_token,
        "minority_interest_rule_version_token": payload.minority_interest_rule_version_token,
        "fx_translation_run_ref_nullable": payload.fx_translation_run_ref_nullable,
        "source_consolidation_run_refs": payload.source_consolidation_run_refs,
        "run_status": payload.run_status,
    }
    return build_token(value)
