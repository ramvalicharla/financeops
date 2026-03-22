from __future__ import annotations

from pydantic import BaseModel, Field


class CanonicalMasterRecord(BaseModel):
    code: str
    name: str
    entity_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class CanonicalMasterData(BaseModel):
    dataset_token: str
    records: list[CanonicalMasterRecord] = Field(default_factory=list)
    
