from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ControlPlaneAuthorizeRequest(BaseModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    module_code: str
    resource_type: str
    resource_id: str
    action: str
    execution_mode: str = Field(pattern="^(api|job|worker|internal)$")
    request_fingerprint: str
    correlation_id: str
    context_scope: dict[str, Any] = Field(default_factory=dict)


class ControlPlaneAuthDecision(BaseModel):
    decision: str = Field(pattern="^(allow|deny|defer)$")
    reason_code: str
    policy_snapshot_version: int
    quota_check_id: str | None = None
    isolation_route_version: int | None = None
    context_token: str | None = None


class ControlPlaneContextTokenClaims(BaseModel):
    tenant_id: uuid.UUID
    module_code: str
    decision: str
    policy_snapshot_version: int
    quota_check_id: str
    isolation_route_version: int
    issued_at: datetime
    expires_at: datetime
    correlation_id: str


class PackageCreateRequest(BaseModel):
    package_code: str = Field(min_length=1, max_length=64)
    package_name: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1.0.0", min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=1024)


class PackageAssignmentRequest(BaseModel):
    package_id: uuid.UUID
    assignment_status: str = Field(default="active", min_length=1, max_length=32)


class ModuleCreateRequest(BaseModel):
    module_code: str = Field(min_length=1, max_length=64)
    module_name: str = Field(min_length=1, max_length=255)
    engine_context: str = Field(default="platform", min_length=1, max_length=64)
    is_financial_impacting: bool = True


class ModuleEnablementRequest(BaseModel):
    module_id: uuid.UUID
    enabled: bool
    enablement_source: str = Field(default="override", min_length=1, max_length=64)


class FinanceExecutionProbeRequest(BaseModel):
    module_code: str = Field(min_length=1, max_length=64)
    resource_type: str = Field(default="finance_execution", min_length=1, max_length=64)
    action: str = Field(default="execute", min_length=1, max_length=64)
    execution_mode: str = Field(default="internal", pattern="^(api|job|worker|internal|export|ai|storage)$")
    request_fingerprint: str = Field(min_length=1, max_length=128)
    resource_id: str = Field(default="probe", min_length=1, max_length=128)
    context_scope: dict[str, Any] = Field(default_factory=dict)
