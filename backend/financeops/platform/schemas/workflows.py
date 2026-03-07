from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowStageCreate(BaseModel):
    stage_order: int = Field(ge=1)
    stage_code: str = Field(min_length=1, max_length=128)
    stage_type: str = Field(pattern="^(review|approval)$")
    approval_mode: str = Field(pattern="^(sequential|parallel)$")
    threshold_type: str = Field(pattern="^(all|any|count)$")
    threshold_value: int | None = Field(default=None, ge=1)
    sla_hours: int | None = Field(default=None, ge=1)
    is_terminal: bool = False
    role_ids: list[str] = Field(default_factory=list)
    user_ids: list[str] = Field(default_factory=list)


class WorkflowTemplateCreate(BaseModel):
    template_code: str = Field(min_length=1, max_length=128)
    module_id: uuid.UUID


class WorkflowTemplateVersionCreate(BaseModel):
    template_id: uuid.UUID
    version_no: int = Field(ge=1)
    effective_from: datetime
    effective_to: datetime | None = None
    stages: list[WorkflowStageCreate] = Field(min_length=1)


class WorkflowInstanceCreate(BaseModel):
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    module_id: uuid.UUID
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: uuid.UUID
    initiated_by: uuid.UUID | None = None


class WorkflowApprovalRequest(BaseModel):
    stage_instance_id: uuid.UUID
    acted_by: uuid.UUID
    decision: str = Field(pattern="^(approve|reject|abstain)$")
    decision_reason: str | None = None
    delegated_from: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(min_length=1, max_length=128)
