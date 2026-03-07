from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class SessionTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reconciliation_type: str
    source_a_type: str
    source_a_ref: str
    source_b_type: str
    source_b_ref: str
    period_start: date
    period_end: date
    matching_rule_version: str
    tolerance_rule_version: str
    materiality_config_json: dict[str, Any]
