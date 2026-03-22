from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class BoardPackRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    board_pack_definition_version_token: str
    section_definition_version_token: str
    narrative_template_version_token: str
    inclusion_rule_version_token: str
    source_metric_run_ids: list[str]
    source_risk_run_ids: list[str]
    source_anomaly_run_ids: list[str]
    status: str
