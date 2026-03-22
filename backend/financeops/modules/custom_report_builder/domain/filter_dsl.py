from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

from financeops.modules.custom_report_builder.domain.enums import (
    FilterOperator,
    ReportExportFormat,
    SortDirection,
)
from financeops.modules.custom_report_builder.domain.metric_registry import (
    validate_metric_keys,
)


class FilterCondition(BaseModel):
    field: str
    operator: FilterOperator
    value: Any


class FilterConfig(BaseModel):
    conditions: list[FilterCondition] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    entity_ids: list[uuid.UUID] = Field(default_factory=list)
    account_codes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    amount_min: str | None = None
    amount_max: str | None = None

    @field_validator("amount_min", "amount_max")
    @classmethod
    def _validate_decimal_str(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("amount bounds must be valid Decimal strings") from exc
        return value


class SortConfig(BaseModel):
    field: str
    direction: SortDirection = SortDirection.ASC


class ReportDefinitionSchema(BaseModel):
    name: str
    description: str | None = None
    metric_keys: list[str]
    filter_config: FilterConfig
    group_by: list[str] = Field(default_factory=list)
    sort_config: SortConfig | None = None
    export_formats: list[ReportExportFormat] = Field(
        default_factory=lambda: [ReportExportFormat.CSV]
    )
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metric_keys")
    @classmethod
    def _validate_metric_keys_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("metric_keys must not be empty")
        invalid = validate_metric_keys(value)
        if invalid:
            raise ValueError(f"Invalid metric keys: {', '.join(invalid)}")
        return value


__all__ = [
    "FilterCondition",
    "FilterConfig",
    "ReportDefinitionSchema",
    "SortConfig",
]

