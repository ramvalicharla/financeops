from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class MappingVersionTokenInput:
    mapping_rows: list[dict[str, Any]]


@dataclass(frozen=True)
class RuleVersionTokenInput:
    rule_rows: list[dict[str, Any]]


@dataclass(frozen=True)
class PayrollGlRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    payroll_run_id: uuid.UUID
    gl_run_id: uuid.UUID
    mapping_version_token: str
    rule_version_token: str
    reporting_period: date

