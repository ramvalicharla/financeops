from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpEntity(FinancialBase):
    __tablename__ = "cp_entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_code", name="uq_cp_entity_code"),
        Index("idx_cp_entities_org", "tenant_id", "organisation_id"),
        Index("idx_cp_entities_group", "tenant_id", "group_id"),
    )

    entity_code: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_organisations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cin: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lei: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fiscal_year_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applicable_gaap: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    registered_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
