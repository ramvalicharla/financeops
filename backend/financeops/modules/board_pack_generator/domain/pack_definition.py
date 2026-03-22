from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType


class SectionConfig(BaseModel):
    section_type: SectionType
    order: int
    title: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class PackDefinitionSchema(BaseModel):
    name: str
    description: str | None = None
    section_configs: list[SectionConfig]
    entity_ids: list[uuid.UUID]
    period_type: PeriodType
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("section_configs")
    @classmethod
    def _validate_section_configs_not_empty(cls, value: list[SectionConfig]) -> list[SectionConfig]:
        if not value:
            raise ValueError("section_configs must not be empty")
        return value

    @field_validator("entity_ids")
    @classmethod
    def _validate_entity_ids_not_empty(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if not value:
            raise ValueError("entity_ids must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_section_orders_unique(self) -> "PackDefinitionSchema":
        orders = [section.order for section in self.section_configs]
        if len(orders) != len(set(orders)):
            raise ValueError("section order values must be unique")
        return self


class PackRunContext(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    definition: PackDefinitionSchema
    period_start: date
    period_end: date
    triggered_by: uuid.UUID

    @model_validator(mode="after")
    def _validate_period_range(self) -> "PackRunContext":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class RenderedSection(BaseModel):
    section_type: SectionType
    section_order: int
    title: str
    data_snapshot: dict[str, Any]
    section_hash: str

    @classmethod
    def _canonicalize_value(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): cls._canonicalize_value(child) for key, child in value.items()}
        if isinstance(value, list):
            return [cls._canonicalize_value(item) for item in value]
        if isinstance(value, tuple):
            return [cls._canonicalize_value(item) for item in value]
        return value

    @classmethod
    def compute_hash(cls, data: dict[str, Any]) -> str:
        canonical_payload = cls._canonicalize_value(data)
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class AssembledPack(BaseModel):
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    period_start: date
    period_end: date
    sections: list[RenderedSection]
    chain_hash: str

    @classmethod
    def compute_chain_hash(cls, sections: list[RenderedSection]) -> str:
        ordered_hashes = [section.section_hash for section in sorted(sections, key=lambda row: row.section_order)]
        return hashlib.sha256("".join(ordered_hashes).encode("utf-8")).hexdigest()


__all__ = [
    "AssembledPack",
    "PackDefinitionSchema",
    "PackRunContext",
    "RenderedSection",
    "SectionConfig",
]

