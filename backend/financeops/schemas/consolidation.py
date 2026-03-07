from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.services.fx.normalization import normalize_currency_code

_MIN_SUPPORTED_YEAR = 2000
_MAX_SUPPORTED_YEAR = 2100


class ConsolidationRateMode(str, Enum):
    month_end_locked = "month_end_locked"
    daily = "daily"


class ConsolidationEntitySnapshotInput(BaseModel):
    entity_id: UUID
    snapshot_id: UUID


class ConsolidationRunRequest(BaseModel):
    period_year: int = Field(ge=_MIN_SUPPORTED_YEAR, le=_MAX_SUPPORTED_YEAR)
    period_month: int = Field(ge=1, le=12)
    parent_currency: str
    rate_mode: ConsolidationRateMode = ConsolidationRateMode.month_end_locked
    entity_snapshots: list[ConsolidationEntitySnapshotInput] = Field(min_length=1, max_length=100)
    amount_tolerance_parent: Decimal | None = Field(default=None, gt=Decimal("0"))
    fx_explained_tolerance_parent: Decimal | None = Field(default=None, gt=Decimal("0"))
    timing_tolerance_days: int | None = Field(default=None, gt=0, le=365)

    @field_validator("parent_currency", mode="before")
    @classmethod
    def _validate_parent_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_uniqueness(self) -> "ConsolidationRunRequest":
        entity_ids = [item.entity_id for item in self.entity_snapshots]
        snapshot_ids = [item.snapshot_id for item in self.entity_snapshots]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity_snapshots contains duplicate entity_id values")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("entity_snapshots contains duplicate snapshot_id values")
        return self


class ConsolidationRunAcceptedResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    correlation_id: str


class ConsolidationRunStatusResponse(BaseModel):
    run_id: str
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None = None


class ConsolidationResultRow(BaseModel):
    consolidated_account_code: str
    consolidated_amount_parent: str
    fx_impact_total: str


class ConsolidationResultsResponse(BaseModel):
    run_id: str
    parent_currency: str
    rows: list[ConsolidationResultRow]
    count: int
    total_consolidated_amount_parent: str
    total_fx_impact_parent: str


class IntercompanyDifferenceRow(BaseModel):
    pair_id: str
    entity_from: str
    entity_to: str
    account_code: str
    ic_reference: str | None
    classification: str
    expected_difference: str
    actual_difference: str
    fx_explained: str
    unexplained_difference: str
    transaction_date_from: date | None
    transaction_date_to: date | None


class IntercompanyDifferencesResponse(BaseModel):
    run_id: str
    rows: list[IntercompanyDifferenceRow]
    count: int


class DrillLineageMetadata(BaseModel):
    parent_reference_id: str | None
    source_reference_id: str | None
    correlation_id: str | None


class AccountDrillEntityRow(DrillLineageMetadata):
    entity_id: str
    local_amount_total: str
    parent_amount_total: str
    fx_delta_total: str
    child_line_item_ids: list[str]


class ConsolidationAccountDrillResponse(DrillLineageMetadata):
    run_id: str
    account_code: str
    child_entity_ids: list[str]
    entities: list[AccountDrillEntityRow]


class EntityDrillLineItemRow(DrillLineageMetadata):
    line_item_id: str
    account_code: str
    local_currency: str
    local_amount: str
    fx_rate_used: str
    parent_amount: str
    fx_delta_component: str
    child_snapshot_line_id: str


class ConsolidationEntityDrillResponse(DrillLineageMetadata):
    run_id: str
    entity_id: str
    child_line_item_ids: list[str]
    line_items: list[EntityDrillLineItemRow]


class SnapshotLineDrillRow(BaseModel):
    snapshot_line_id: str
    snapshot_id: str
    account_code: str
    local_amount: str
    currency: str
    ic_reference: str | None
    counterparty_entity: str | None
    transaction_date: date | None
    ic_account_class: str | None


class LineItemDrillRow(BaseModel):
    line_item_id: str
    entity_id: str
    account_code: str
    local_currency: str
    local_amount: str
    fx_rate_used: str
    expected_rate: str
    parent_amount: str
    fx_delta_component: str
    ic_reference: str | None
    ic_counterparty_entity: str | None
    transaction_date: date | None


class ConsolidationLineItemDrillResponse(DrillLineageMetadata):
    run_id: str
    line_item_id: str
    child_snapshot_line_id: str
    line_item: LineItemDrillRow
    snapshot_line: SnapshotLineDrillRow | None


class ConsolidationSnapshotLineDrillResponse(DrillLineageMetadata):
    run_id: str
    snapshot_line_id: str
    child_references: list[dict[str, str]]
    snapshot_line: SnapshotLineDrillRow
