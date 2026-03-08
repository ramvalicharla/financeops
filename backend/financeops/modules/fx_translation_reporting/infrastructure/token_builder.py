from __future__ import annotations

from financeops.modules.fx_translation_reporting.domain.value_objects import (
    DefinitionVersionTokenInput,
    FxTranslationRunTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_fx_translation_run_token(payload: FxTranslationRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "reporting_currency_code": payload.reporting_currency_code,
        "reporting_currency_version_token": payload.reporting_currency_version_token,
        "translation_rule_version_token": payload.translation_rule_version_token,
        "rate_policy_version_token": payload.rate_policy_version_token,
        "rate_source_version_token": payload.rate_source_version_token,
        "source_consolidation_run_refs": payload.source_consolidation_run_refs,
        "run_status": payload.run_status,
    }
    return build_token(value)

