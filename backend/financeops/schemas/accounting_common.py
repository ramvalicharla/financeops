from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DrillResponseBase(BaseModel):
    id: UUID
    parent_reference_id: UUID | None = None
    source_reference_id: UUID | None = None
    correlation_id: UUID
    child_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("child_ids")
    @classmethod
    def _normalize_child_ids(cls, value: list[UUID]) -> list[UUID]:
        unique_child_ids = {item for item in value}
        return sorted(unique_child_ids, key=str)
