from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ConsolidationRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    hierarchy_version_token: str
    scope_version_token: str
    rule_version_token: str
    intercompany_version_token: str
    adjustment_version_token: str
    source_run_refs: list[dict[str, Any]]
    run_status: str

