from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class PrepaidSchedule(Base):
    __tablename__ = "prepaid_schedules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_id",
            "reference_number",
            name="uq_prepaid_schedules_tenant_entity_reference",
        ),
        Index("idx_prepaid_schedules_tenant_id", "tenant_id"),
        Index("idx_prepaid_schedules_entity_id", "entity_id"),
        Index("idx_prepaid_schedules_reference_number", "reference_number"),
        Index("idx_prepaid_schedules_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    reference_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    prepaid_type: Mapped[str] = mapped_column(String(30), nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amortised_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, server_default=text("0"), default=Decimal("0"))
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    coverage_start: Mapped[date] = mapped_column(Date, nullable=False)
    coverage_end: Mapped[date] = mapped_column(Date, nullable=False)
    amortisation_method: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'SLM'"), default="SLM")
    coa_prepaid_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    coa_expense_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PrepaidAmortisationEntry(Base):
    __tablename__ = "prepaid_amortisation_entries"
    __table_args__ = (
        UniqueConstraint("run_reference", name="uq_prepaid_amortisation_entries_run_reference"),
        Index("idx_prepaid_amortisation_entries_tenant_id", "tenant_id"),
        Index("idx_prepaid_amortisation_entries_entity_id", "entity_id"),
        Index("idx_prepaid_amortisation_entries_schedule_id", "schedule_id"),
        Index("idx_prepaid_amortisation_entries_period_start", "period_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepaid_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amortisation_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    is_last_period: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    run_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = ["PrepaidSchedule", "PrepaidAmortisationEntry"]
