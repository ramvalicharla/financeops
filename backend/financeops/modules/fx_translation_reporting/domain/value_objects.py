from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class FxTranslationRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    reporting_currency_code: str
    reporting_currency_version_token: str
    translation_rule_version_token: str
    rate_policy_version_token: str
    rate_source_version_token: str
    source_consolidation_run_refs: list[dict[str, Any]]
    run_status: str

