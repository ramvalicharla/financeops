from __future__ import annotations

from financeops.modules.financial_risk_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
    RiskRunTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_risk_run_token(payload: RiskRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "risk_definition_version_token": payload.risk_definition_version_token,
        "propagation_version_token": payload.propagation_version_token,
        "weight_version_token": payload.weight_version_token,
        "materiality_version_token": payload.materiality_version_token,
        "source_metric_run_ids": payload.source_metric_run_ids,
        "source_variance_run_ids": payload.source_variance_run_ids,
        "source_trend_run_ids": payload.source_trend_run_ids,
        "source_reconciliation_session_ids": payload.source_reconciliation_session_ids,
        "status": payload.status,
    }
    return build_token(
        value,
        sorted_list_fields=(
            "source_metric_run_ids",
            "source_variance_run_ids",
            "source_trend_run_ids",
            "source_reconciliation_session_ids",
        ),
    )
