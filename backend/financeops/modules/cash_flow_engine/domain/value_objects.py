from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class CashFlowRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    statement_definition_version_token: str
    line_mapping_version_token: str
    bridge_rule_version_token: str
    source_consolidation_run_ref: str
    source_fx_translation_run_ref_nullable: str | None
    source_ownership_consolidation_run_ref_nullable: str | None
    run_status: str
