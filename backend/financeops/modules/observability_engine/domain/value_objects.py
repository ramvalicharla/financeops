from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ObservabilityOperationTokenInput:
    tenant_id: UUID
    operation_type: str
    input_ref_json: dict[str, Any]


@dataclass(frozen=True)
class DiffTokenInput:
    tenant_id: UUID
    base_run_id: UUID
    compare_run_id: UUID
    base_run_token: str
    compare_run_token: str


@dataclass(frozen=True)
class RegistrySnapshot:
    module_code: str
    run_id: UUID
    run_token: str
    version_token_snapshot: dict[str, Any]
    dependencies: list[dict[str, Any]]
    status: str
    reporting_period: date | None = None
