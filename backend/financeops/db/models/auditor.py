from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class AuditorGrant(FinancialBase):
    """
    Auditor access grant — INSERT ONLY.
    tenant_id = the tenant BEING AUDITED (the one granting access).
    To revoke: insert a new row with is_active=False and revoked_at set.
    """
    __tablename__ = "auditor_grants"
    __table_args__ = (
        Index("idx_auditor_grants_tenant", "tenant_id"),
        Index("idx_auditor_grants_auditor", "auditor_user_id"),
        Index("idx_auditor_grants_active", "tenant_id", "auditor_user_id", "is_active"),
    )

    auditor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # scope: full / limited
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="limited")
    # JSON list of allowed module names, e.g. ["mis_manager", "reconciliation"]
    allowed_modules: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: {"modules": []}
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditorAccessLog(FinancialBase):
    """
    Immutable log of every auditor data access event — INSERT ONLY.
    tenant_id = the tenant whose data was accessed.
    """
    __tablename__ = "auditor_access_logs"
    __table_args__ = (
        Index("idx_auditor_logs_tenant", "tenant_id", "created_at"),
        Index("idx_auditor_logs_auditor", "auditor_user_id", "created_at"),
    )

    grant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    auditor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accessed_resource: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # access_result: granted / denied
    access_result: Mapped[str] = mapped_column(String(20), nullable=False, default="granted")
