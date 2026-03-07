from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IsolationPolicyCreate(BaseModel):
    isolation_tier: str = Field(pattern="^(tier1|tier2|tier3|tier4)$")
    db_cluster: str = Field(min_length=1, max_length=128)
    schema_name: str = Field(min_length=1, max_length=128)
    worker_pool: str = Field(min_length=1, max_length=128)
    region: str = Field(min_length=1, max_length=64)
    migration_state: str
    route_version: int = Field(ge=1)
    effective_from: datetime
    effective_to: datetime | None = None


class IsolationRoute(BaseModel):
    tenant_id: uuid.UUID
    db_cluster: str
    schema_name: str
    worker_pool: str
    region: str
    route_version: int
    migration_state: str
