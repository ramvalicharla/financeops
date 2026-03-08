from __future__ import annotations

from financeops.modules.anomaly_pattern_engine.domain.value_objects import (
    AnomalyRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return sha256_hex_text(canonical_json_dumps(payload.rows))


def build_anomaly_run_token(payload: AnomalyRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "anomaly_definition_version_token": payload.anomaly_definition_version_token,
        "pattern_rule_version_token": payload.pattern_rule_version_token,
        "persistence_rule_version_token": payload.persistence_rule_version_token,
        "correlation_rule_version_token": payload.correlation_rule_version_token,
        "statistical_rule_version_token": payload.statistical_rule_version_token,
        "source_metric_run_ids": sorted(payload.source_metric_run_ids),
        "source_variance_run_ids": sorted(payload.source_variance_run_ids),
        "source_trend_run_ids": sorted(payload.source_trend_run_ids),
        "source_risk_run_ids": sorted(payload.source_risk_run_ids),
        "source_reconciliation_session_ids": sorted(payload.source_reconciliation_session_ids),
        "status": payload.status,
    }
    return sha256_hex_text(canonical_json_dumps(value))
