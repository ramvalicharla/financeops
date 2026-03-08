from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class OwnershipRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    hierarchy_version_token: str
    scope_version_token: str
    ownership_structure_version_token: str
    ownership_rule_version_token: str
    minority_interest_rule_version_token: str
    fx_translation_run_ref_nullable: str | None
    source_consolidation_run_refs: list[dict[str, Any]]
    run_status: str
