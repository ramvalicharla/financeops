from __future__ import annotations

from pydantic import BaseModel

from financeops.modules.erp_sync.domain.enums import DatasetType


class PeriodResolution(BaseModel):
    granularity: str
    period_start: str | None = None
    period_end: str | None = None
    as_at_date: str | None = None


class ExtractionScope(BaseModel):
    include_entities: list[str] = []
    include_dimensions: dict[str, list[str]] = {}


class SyncDefinitionModel(BaseModel):
    dataset_type: DatasetType
    period_resolution: PeriodResolution
    extraction_scope: ExtractionScope
