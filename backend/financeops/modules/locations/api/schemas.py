from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationCreateRequest(BaseModel):
    entity_id: uuid.UUID
    location_name: str = Field(min_length=1, max_length=200)
    location_code: str = Field(min_length=1, max_length=50)
    gstin: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=5)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country_code: str = Field(default="IND", max_length=3)
    is_primary: bool = False
    is_active: bool = True


class LocationUpdateRequest(BaseModel):
    location_name: str | None = Field(default=None, min_length=1, max_length=200)
    location_code: str | None = Field(default=None, min_length=1, max_length=50)
    gstin: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=5)
    address_line1: str | None = Field(default=None, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country_code: str | None = Field(default=None, max_length=3)
    is_primary: bool | None = None
    is_active: bool | None = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    location_name: str
    location_code: str
    gstin: str | None = None
    state_code: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country_code: str
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class CostCentreCreateRequest(BaseModel):
    entity_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    cost_centre_code: str = Field(min_length=1, max_length=50)
    cost_centre_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_active: bool = True


class CostCentreUpdateRequest(BaseModel):
    parent_id: uuid.UUID | None = None
    cost_centre_code: str | None = Field(default=None, min_length=1, max_length=50)
    cost_centre_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class CostCentreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    cost_centre_code: str
    cost_centre_name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class CostCentreTreeNode(CostCentreResponse):
    children: list["CostCentreTreeNode"] = Field(default_factory=list)


class GstinValidationResponse(BaseModel):
    valid: bool
    state_code: str | None = None
    state_name: str | None = None


class StateCodeResponse(BaseModel):
    code: str
    name: str


CostCentreTreeNode.model_rebuild()

