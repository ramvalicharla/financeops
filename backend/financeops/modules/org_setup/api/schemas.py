from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntityTypeLiteral = Literal[
    "WHOLLY_OWNED_SUBSIDIARY",
    "JOINT_VENTURE",
    "ASSOCIATE",
    "BRANCH",
    "REPRESENTATIVE_OFFICE",
    "HOLDING_COMPANY",
    "PARTNERSHIP",
    "LLP",
    "TRUST",
    "SOLE_PROPRIETORSHIP",
]

GaapLiteral = Literal["INDAS", "IFRS", "USGAAP", "MANAGEMENT"]

ErpTypeLiteral = Literal[
    "TALLY_PRIME",
    "TALLY_ERP9",
    "ZOHO_BOOKS",
    "QUICKBOOKS_ONLINE",
    "QUICKBOOKS_DESKTOP",
    "NETSUITE",
    "SAP_B1",
    "SAP_S4",
    "ORACLE_FUSION",
    "DYNAMICS_365",
    "XERO",
    "BUSY",
    "MARG",
    "MANUAL",
]

CoaStatusLiteral = Literal["pending", "uploaded", "skipped", "erp_connected"]

ConsolidationMethodLiteral = Literal[
    "FULL_CONSOLIDATION",
    "EQUITY_METHOD",
    "PROPORTIONATE",
    "EXCLUDED",
]


class OrgGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    group_name: str
    country_of_incorp: str
    country_code: str
    functional_currency: str
    reporting_currency: str
    logo_url: str | None = None
    website: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class Step1Request(BaseModel):
    group_name: str = Field(min_length=1, max_length=300)
    country_of_incorp: str = Field(min_length=1, max_length=100)
    country_code: str = Field(min_length=2, max_length=3)
    functional_currency: str = Field(min_length=3, max_length=10)
    reporting_currency: str = Field(min_length=3, max_length=10)
    logo_url: str | None = None
    website: str | None = None


class Step1Response(BaseModel):
    group: OrgGroupResponse


class Step2EntityRequest(BaseModel):
    legal_name: str = Field(min_length=1, max_length=300)
    display_name: str | None = Field(default=None, max_length=200)
    entity_type: EntityTypeLiteral
    country_code: str = Field(min_length=2, max_length=3)
    state_code: str | None = Field(default=None, max_length=10)
    functional_currency: str = Field(min_length=3, max_length=10)
    reporting_currency: str = Field(min_length=3, max_length=10)
    fiscal_year_start: int = Field(ge=1, le=12)
    applicable_gaap: GaapLiteral
    incorporation_number: str | None = Field(default=None, max_length=100)
    pan: str | None = Field(default=None, max_length=20)
    tan: str | None = Field(default=None, max_length=20)
    cin: str | None = Field(default=None, max_length=30)
    gstin: str | None = Field(default=None, max_length=20)
    lei: str | None = Field(default=None, max_length=30)
    tax_jurisdiction: str | None = Field(default=None, max_length=100)
    tax_rate: Decimal | None = None
    registered_address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)


class Step2Request(BaseModel):
    group_id: uuid.UUID
    entities: list[Step2EntityRequest]


class OrgEntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    org_group_id: uuid.UUID
    cp_entity_id: uuid.UUID | None = None
    legal_name: str
    display_name: str | None = None
    entity_type: EntityTypeLiteral
    country_code: str
    state_code: str | None = None
    functional_currency: str
    reporting_currency: str
    fiscal_year_start: int
    applicable_gaap: GaapLiteral
    industry_template_id: uuid.UUID | None = None
    incorporation_number: str | None = None
    pan: str | None = None
    tan: str | None = None
    cin: str | None = None
    gstin: str | None = None
    lei: str | None = None
    tax_jurisdiction: str | None = None
    tax_rate: Decimal | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class Step2Response(BaseModel):
    entities: list[OrgEntityResponse]


class OwnershipRequest(BaseModel):
    parent_entity_id: uuid.UUID
    child_entity_id: uuid.UUID
    ownership_pct: Decimal
    manual_consolidation_method: ConsolidationMethodLiteral | None = None
    effective_from: date
    notes: str | None = None


class OrgOwnershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    parent_entity_id: uuid.UUID
    child_entity_id: uuid.UUID
    ownership_pct: Decimal
    consolidation_method: ConsolidationMethodLiteral
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    created_at: datetime


class Step3Request(BaseModel):
    relationships: list[OwnershipRequest]


class Step3Response(BaseModel):
    ownership: list[OrgOwnershipResponse]


class ErpConfigRequest(BaseModel):
    org_entity_id: uuid.UUID
    erp_type: ErpTypeLiteral
    erp_version: str | None = None
    is_primary: bool = True


class OrgEntityErpConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    org_entity_id: uuid.UUID
    erp_type: ErpTypeLiteral
    erp_version: str | None = None
    connection_config: dict[str, object] | None = None
    is_primary: bool
    connection_tested: bool
    connection_tested_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class Step4Request(BaseModel):
    configs: list[ErpConfigRequest]


class Step4Response(BaseModel):
    configs: list[OrgEntityErpConfigResponse]


class EntityTemplateRequest(BaseModel):
    entity_id: uuid.UUID
    template_id: uuid.UUID


class Step5Request(BaseModel):
    entity_templates: list[EntityTemplateRequest]


class Step5EntitySummary(BaseModel):
    entity_id: uuid.UUID
    template_code: str
    account_count: int


class Step5Response(BaseModel):
    initialised_count: int
    entity_summaries: list[Step5EntitySummary]
    coa_status: CoaStatusLiteral = "pending"
    onboarding_score: int = Field(default=0, ge=0, le=100)


class Step6Request(BaseModel):
    confirmed_mapping_ids: list[uuid.UUID]
    auto_confirm_above: str | None = None


class Step6Response(BaseModel):
    confirmed_count: int
    unmapped_count: int
    setup_complete: bool
    coa_status: CoaStatusLiteral = "pending"
    onboarding_score: int = Field(default=0, ge=0, le=100)


class OrgSetupProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    current_step: int
    step1_data: dict[str, object] | None = None
    step2_data: dict[str, object] | None = None
    step3_data: dict[str, object] | None = None
    step4_data: dict[str, object] | None = None
    step5_data: dict[str, object] | None = None
    step6_data: dict[str, object] | None = None
    coa_status: CoaStatusLiteral = "pending"
    onboarding_score: int = Field(default=0, ge=0, le=100)
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrgSetupSummaryResponse(BaseModel):
    group: OrgGroupResponse | None = None
    entities: list[OrgEntityResponse]
    ownership: list[OrgOwnershipResponse]
    erp_configs: list[OrgEntityErpConfigResponse]
    current_step: int = Field(default=1, ge=1, le=4)
    completed_at: datetime | None = None
    coa_account_count: int
    coa_status: CoaStatusLiteral = "pending"
    onboarding_score: int = Field(default=0, ge=0, le=100)
    mapping_summary: dict[str, int | Decimal]


class OwnershipTreeNode(BaseModel):
    entity_id: str
    legal_name: str
    display_name: str | None = None
    entity_type: str
    ownership_pct: Decimal | None = None
    consolidation_method: str | None = None
    children: list["OwnershipTreeNode"] = Field(default_factory=list)


class OwnershipTreeResponse(BaseModel):
    group_id: str | None = None
    group_name: str | None = None
    entities: list[OwnershipTreeNode]


class UpdateOrgEntityRequest(BaseModel):
    display_name: str | None = None
    entity_type: EntityTypeLiteral | None = None
    country_code: str | None = None
    state_code: str | None = None
    functional_currency: str | None = None
    reporting_currency: str | None = None
    fiscal_year_start: int | None = Field(default=None, ge=1, le=12)
    applicable_gaap: GaapLiteral | None = None
    incorporation_number: str | None = None
    pan: str | None = None
    tan: str | None = None
    cin: str | None = None
    gstin: str | None = None
    lei: str | None = None
    tax_jurisdiction: str | None = None
    tax_rate: Decimal | None = None
    registered_address: str | None = None
    city: str | None = None
    pincode: str | None = None
    is_active: bool | None = None


OwnershipTreeNode.model_rebuild()
