from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class EquityRunTokenInput:
    tenant_id: UUID
    organisation_id: UUID
    reporting_period: date
    statement_definition_version_token: str
    line_definition_version_token: str
    rollforward_rule_version_token: str
    source_mapping_version_token: str
    consolidation_run_ref_nullable: str | None
    fx_translation_run_ref_nullable: str | None
    ownership_consolidation_run_ref_nullable: str | None
    run_status: str
