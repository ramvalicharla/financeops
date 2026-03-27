from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, event, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base
from financeops.platform.db.models.entities import CpEntity


class StatutoryRegisterEntry(Base):
    __tablename__ = "statutory_register_entries"
    __table_args__ = (
        Index("idx_statutory_register_entries_tenant_type", "tenant_id", "register_type", "entry_date"),
        Index("idx_statutory_register_entries_tenant_entity", "tenant_id", "entity_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    register_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_description: Mapped[str] = mapped_column(Text, nullable=False)
    folio_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reference_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class StatutoryFiling(Base):
    __tablename__ = "statutory_filings"
    __table_args__ = (
        Index("idx_statutory_filings_tenant_due_status", "tenant_id", "due_date", "status"),
        Index("idx_statutory_filings_tenant_entity", "tenant_id", "entity_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    form_number: Mapped[str] = mapped_column(String(20), nullable=False)
    form_description: Mapped[str] = mapped_column(String(300), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    filed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"), default="pending")
    filing_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    penalty_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"), default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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


@event.listens_for(StatutoryRegisterEntry, "before_insert")
def _set_register_entity_id(mapper, connection, target: StatutoryRegisterEntry) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


@event.listens_for(StatutoryFiling, "before_insert")
def _set_filing_entity_id(mapper, connection, target: StatutoryFiling) -> None:
    del mapper
    if target.entity_id is not None:
        return
    resolved = _resolve_entity_id_from_tenant(connection, target.tenant_id)
    if resolved is not None:
        target.entity_id = resolved


__all__ = ["StatutoryRegisterEntry", "StatutoryFiling"]
