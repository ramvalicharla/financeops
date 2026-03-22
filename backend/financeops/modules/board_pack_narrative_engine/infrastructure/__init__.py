from __future__ import annotations

from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
    BoardPackRunTokenInput,
    DefinitionVersionTokenInput,
)
from financeops.shared_kernel.tokens import build_token, build_version_rows_token


def build_definition_version_token(payload: DefinitionVersionTokenInput) -> str:
    return build_version_rows_token(payload.rows)


def build_board_pack_run_token(payload: BoardPackRunTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reporting_period": payload.reporting_period.isoformat(),
        "board_pack_definition_version_token": payload.board_pack_definition_version_token,
        "section_definition_version_token": payload.section_definition_version_token,
        "narrative_template_version_token": payload.narrative_template_version_token,
        "inclusion_rule_version_token": payload.inclusion_rule_version_token,
        "source_metric_run_ids": payload.source_metric_run_ids,
        "source_risk_run_ids": payload.source_risk_run_ids,
        "source_anomaly_run_ids": payload.source_anomaly_run_ids,
        "status": payload.status,
    }
    return build_token(
        value,
        sorted_list_fields=(
            "source_metric_run_ids",
            "source_risk_run_ids",
            "source_anomaly_run_ids",
        ),
    )
