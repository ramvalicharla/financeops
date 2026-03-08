from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class DiffRequest(BaseModel):
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID


class DiffResponse(BaseModel):
    diff_id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    drift_flag: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    idempotent: bool = False


class ReplayValidateResponse(BaseModel):
    run_id: uuid.UUID
    module_code: str
    stored_run_token: str
    recomputed_run_token: str
    matches: bool


class GraphResponse(BaseModel):
    graph_snapshot_id: uuid.UUID
    root_run_id: uuid.UUID
    deterministic_hash: str
    graph: dict[str, Any] = Field(default_factory=dict)

