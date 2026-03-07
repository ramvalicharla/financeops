from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class MetricRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    scope_json: dict[str, Any]
    mis_snapshot_id: uuid.UUID | None
    payroll_run_id: uuid.UUID | None
    gl_run_id: uuid.UUID | None
    reconciliation_session_id: uuid.UUID | None
    payroll_gl_reconciliation_run_id: uuid.UUID | None
    metric_definition_version_token: str
    variance_definition_version_token: str
    trend_definition_version_token: str
    materiality_rule_version_token: str
    input_signature_hash: str
