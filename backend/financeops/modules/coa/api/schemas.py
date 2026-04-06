from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class CoaTemplateResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_active: bool


class CoaLedgerAccountResponse(BaseModel):
    id: uuid.UUID
    account_subgroup_id: uuid.UUID
    industry_template_id: uuid.UUID
    code: str
    name: str
    source_type: str
    tenant_id: uuid.UUID | None = None
    version: int
    description: str | None = None
    normal_balance: str
    cash_flow_tag: str | None = None
    cash_flow_method: str | None = None
    bs_pl_flag: str | None = None
    asset_liability_class: str | None = None
    is_monetary: bool
    is_related_party: bool
    is_tax_deductible: bool
    is_control_account: bool
    notes_reference: str | None = None
    is_active: bool
    sort_order: int
    created_by: uuid.UUID | None = None


class CoaUploadResponse(BaseModel):
    batch_id: uuid.UUID
    upload_status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class CoaValidateResponse(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class CoaApplyRequest(BaseModel):
    batch_id: uuid.UUID


class CoaApplyResponse(BaseModel):
    batch_id: uuid.UUID
    applied_rows: int
    template_id: uuid.UUID
    source_type: str


class CoaSkipResponse(BaseModel):
    coa_status: Literal["pending", "uploaded", "skipped", "erp_connected"]
    next_step: int
    onboarding_score: int


class CoaUploadModeRequest(BaseModel):
    mode: Literal["APPEND", "REPLACE", "VALIDATE_ONLY"] = "APPEND"


class CoaUploadBatchResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    source_type: str
    upload_mode: str
    file_name: str
    upload_status: str
    error_log: dict[str, Any] | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    processed_at: datetime | None = None


class CoaHierarchyLedgerAccount(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    normal_balance: str
    cash_flow_tag: str | None = None
    bs_pl_flag: str | None = None
    asset_liability_class: str | None = None


class CoaHierarchySubgroup(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    ledger_accounts: list[CoaHierarchyLedgerAccount] = Field(default_factory=list)


class CoaHierarchyGroup(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    account_subgroups: list[CoaHierarchySubgroup] = Field(default_factory=list)


class CoaHierarchySubline(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    account_groups: list[CoaHierarchyGroup] = Field(default_factory=list)


class CoaHierarchyLineItem(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    sublines: list[CoaHierarchySubline] = Field(default_factory=list)


class CoaHierarchySchedule(BaseModel):
    id: str
    gaap: str
    code: str
    name: str
    sort_order: int
    line_items: list[CoaHierarchyLineItem] = Field(default_factory=list)


class CoaHierarchyClassification(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    schedules: list[CoaHierarchySchedule] = Field(default_factory=list)


class CoaHierarchyResponse(BaseModel):
    template: dict[str, str | None]
    classifications: list[CoaHierarchyClassification]


class TenantCoaInitialiseRequest(BaseModel):
    template_id: uuid.UUID


class TenantCoaCreateRequest(BaseModel):
    parent_subgroup_id: uuid.UUID
    account_code: str
    display_name: str


class TenantCoaUpdateRequest(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None


class TenantCoaAccountResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    ledger_account_id: uuid.UUID | None = None
    parent_subgroup_id: uuid.UUID | None = None
    account_code: str
    display_name: str
    is_custom: bool
    is_active: bool
    sort_order: int | None = None
    platform_account_code: str | None = None
    platform_account_name: str | None = None
    bs_pl_flag: str | None = None
    asset_liability_class: str | None = None
    normal_balance: str | None = None


class ErpAccountInput(BaseModel):
    code: str
    name: str
    type: str | None = None


class ErpAutoSuggestRequest(BaseModel):
    entity_id: uuid.UUID
    erp_connector_type: str
    erp_accounts: list[ErpAccountInput]


class ErpConfirmRequest(BaseModel):
    tenant_coa_account_id: uuid.UUID


class ErpBulkConfirmRequest(BaseModel):
    mapping_ids: list[uuid.UUID]
    auto_confirm_above: str | None = None


class ErpMappingResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    erp_connector_type: str
    erp_account_code: str
    erp_account_name: str
    erp_account_type: str | None = None
    tenant_coa_account_id: uuid.UUID | None = None
    mapping_confidence: Decimal | None = None
    is_auto_mapped: bool
    is_confirmed: bool
    confirmed_by: uuid.UUID | None = None
    confirmed_at: datetime | None = None
    is_active: bool


class ErpMappingSummaryResponse(BaseModel):
    total: int
    mapped: int
    confirmed: int
    unmapped: int
    confidence_avg: Decimal


class RawTBLineInput(BaseModel):
    erp_account_code: str
    erp_account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str = "INR"
    period_start: date | None = None
    period_end: date | None = None


class TrialBalanceClassifyRequest(BaseModel):
    entity_id: uuid.UUID
    raw_tb: list[RawTBLineInput]
    gaap: str = "INDAS"


class TrialBalanceClassifyMultiEntityRequest(BaseModel):
    entity_raw_tbs: dict[str, list[RawTBLineInput]]
    gaap: str = "INDAS"


class ClassifiedTBLineResponse(BaseModel):
    erp_account_code: str
    erp_account_name: str
    tenant_coa_account_id: uuid.UUID | None = None
    platform_account_code: str | None = None
    platform_account_name: str | None = None
    fs_classification: str | None = None
    fs_schedule: str | None = None
    fs_line_item: str | None = None
    fs_subline: str | None = None
    debit_amount: Decimal
    credit_amount: Decimal
    net_amount: Decimal
    currency: str
    is_unmapped: bool
    is_unconfirmed: bool


class GlobalTBResponse(BaseModel):
    entity_results: dict[str, list[ClassifiedTBLineResponse]]
    consolidated: list[ClassifiedTBLineResponse]
    unmapped_lines: list[ClassifiedTBLineResponse]
    unconfirmed_lines: list[ClassifiedTBLineResponse]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool
    unmapped_count: int
    unconfirmed_count: int
