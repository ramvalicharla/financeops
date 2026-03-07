from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OrganisationCreate(BaseModel):
    organisation_code: str = Field(min_length=1, max_length=64)
    organisation_name: str = Field(min_length=1, max_length=255)
    parent_organisation_id: uuid.UUID | None = None


class GroupCreate(BaseModel):
    group_code: str = Field(min_length=1, max_length=64)
    group_name: str = Field(min_length=1, max_length=255)
    organisation_id: uuid.UUID


class EntityCreate(BaseModel):
    entity_code: str = Field(min_length=1, max_length=64)
    entity_name: str = Field(min_length=1, max_length=255)
    organisation_id: uuid.UUID
    group_id: uuid.UUID | None = None
    base_currency: str = Field(min_length=3, max_length=3)
    country_code: str = Field(min_length=2, max_length=2)

    @field_validator("base_currency", "country_code")
    @classmethod
    def _uppercase_fields(cls, value: str) -> str:
        return value.upper()


class UserOrganisationAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    organisation_id: uuid.UUID
    is_primary: bool = False
    effective_from: datetime
    effective_to: datetime | None = None


class UserEntityAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    entity_id: uuid.UUID
    effective_from: datetime
    effective_to: datetime | None = None
