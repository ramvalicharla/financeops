from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, event, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base
from financeops.platform.db.models.entities import CpEntity


class AuditorPortalAccess(Base):
    __tablename__ = "auditor_portal_access"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_id",
            "auditor_email",
            "engagement_name",
            name="uq_auditor_portal_access_tenant_entity_email_engagement",
        ),
        Index("idx_auditor_portal_access_tenant_engagement", "tenant_id", "engagement_name"),
        Index("idx_auditor_portal_access_tenant_entity", "tenant_id", "entity_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
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
        Index("idx_auditor_requests_tenant_entity", "tenant_id", "entity_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    access_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
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


def _resolve_entity_id_from_tenant(connection, tenant_id: uuid.UUID | None) -> uuid.UUID | None:
    if tenant_id is None:
        return None
    entity_id = connection.execute(
        select(CpEntity.id)
        .where(
            CpEntity.tenant_id == tenant_id,
            CpEntity.status == "active",
        )
        .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if entity_id is not None:
        return entity_id
    return connection.execute(
        select(CpEntity.id)
        .where(CpEntity.status == "active")
        .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        .limit(1)
    ).scalar_one_or_none()


@event.listens_for(AuditorPortalAccess, "before_insert")
def _set_auditor_access_entity_id(mapper, connection, target: AuditorPortalAccess) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


@event.listens_for(AuditorRequest, "before_insert")
def _set_auditor_request_entity_id(mapper, connection, target: AuditorRequest) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


__all__ = ["AuditorPortalAccess", "AuditorRequest"]
