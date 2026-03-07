from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class TenantOnboardingRequest(BaseModel):
    tenant_code: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=2, max_length=255)
    country_code: str = Field(min_length=2, max_length=2)
    region: str = Field(min_length=2, max_length=64)
    billing_tier: str = Field(min_length=2, max_length=64)
    package_code: str = Field(min_length=2, max_length=64)
    admin_user_id: uuid.UUID


class TenantOnboardingResponse(BaseModel):
    tenant_id: uuid.UUID
    onboarding_status: str
    workflow_id: str
    correlation_id: str
