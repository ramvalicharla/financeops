from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    role_code: str = Field(min_length=1, max_length=64)
    role_scope: str = Field(min_length=1, max_length=32)
    inherits_role_id: uuid.UUID | None = None
    is_active: bool = True


class PermissionCreate(BaseModel):
    permission_code: str = Field(min_length=1, max_length=128)
    resource_type: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)


class RolePermissionGrant(BaseModel):
    role_id: uuid.UUID
    permission_id: uuid.UUID
    effect: str = Field(pattern="^(allow|deny)$")


class UserRoleAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID
    context_type: str
    context_id: uuid.UUID | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    assigned_by: uuid.UUID | None = None
