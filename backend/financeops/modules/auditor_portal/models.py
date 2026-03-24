from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class AuditorPortalAccess(Base):
    __tablename__ = "auditor_portal_access"
    __table_args__ = (
        UniqueConstraint("tenant_id", "auditor_email", "engagement_name", name="uq_auditor_portal_access_tenant_email_engagement"),
        Index("idx_auditor_portal_access_tenant_engagement", "tenant_id", "engagement_name"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    auditor_email: Mapped[str] = mapped_column(String(300), nullable=False)
    auditor_firm: Mapped[str] = mapped_column(String(300), nullable=False)
    engagement_name: Mapped[str] = mapped_column(String(300), nullable=False)
    access_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'read_only'"), default="read_only")
    modules_accessible: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class AuditorRequest(Base):
    __tablename__ = "auditor_requests"
    __table_args__ = (
        Index("idx_auditor_requests_access_status", "access_id", "status"),
        Index("idx_auditor_requests_tenant_status_due", "tenant_id", "status", "due_date"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    access_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_number: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"), default="open")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    provided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


__all__ = ["AuditorPortalAccess", "AuditorRequest"]
