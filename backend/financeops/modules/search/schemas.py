from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SearchModule = Literal["journal", "expense", "report", "user", "entity"]


class UnifiedSearchItem(BaseModel):
    id: str
    module: SearchModule
    title: str
    subtitle: str | None = None
    href: str
    status: str | None = None
    amount: float | None = None
    currency: str | None = None
    created_at: datetime


class UnifiedSearchMeta(BaseModel):
    query: str
    total_results: int
    limit: int
    offset: int
    query_time_ms: int = Field(ge=0)


class UnifiedSearchResponse(BaseModel):
    data: list[UnifiedSearchItem]
    meta: UnifiedSearchMeta


__all__ = [
    "SearchModule",
    "UnifiedSearchItem",
    "UnifiedSearchMeta",
    "UnifiedSearchResponse",
]
