from __future__ import annotations

from financeops.modules.reconciliation_bridge.domain.value_objects import (
    SessionTokenInput,
)
from financeops.shared_kernel.tokens import build_token


def build_session_token(payload: SessionTokenInput) -> str:
    value = {
        "tenant_id": str(payload.tenant_id),
        "organisation_id": str(payload.organisation_id),
        "reconciliation_type": payload.reconciliation_type,
        "source_a_type": payload.source_a_type,
        "source_a_ref": payload.source_a_ref,
        "source_b_type": payload.source_b_type,
        "source_b_ref": payload.source_b_ref,
        "period_start": payload.period_start.isoformat(),
        "period_end": payload.period_end.isoformat(),
        "matching_rule_version": payload.matching_rule_version,
        "tolerance_rule_version": payload.tolerance_rule_version,
        "materiality_config_json": payload.materiality_config_json,
    }
    return build_token(value)
