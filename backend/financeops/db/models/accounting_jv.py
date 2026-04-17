from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import FinancialBase


class JVStatus:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PUSH_IN_PROGRESS = "PUSH_IN_PROGRESS"
    PUSHED = "PUSHED"
    PUSH_FAILED = "PUSH_FAILED"
    REJECTED = "REJECTED"
    RESUBMITTED = "RESUBMITTED"
    ESCALATED = "ESCALATED"
    VOIDED = "VOIDED"

    ALL: frozenset[str] = frozenset(
        {
            DRAFT,
            SUBMITTED,
            PENDING_REVIEW,
            UNDER_REVIEW,
            APPROVED,
            PUSH_IN_PROGRESS,
            PUSHED,
            PUSH_FAILED,
            REJECTED,
            RESUBMITTED,
            ESCALATED,
            VOIDED,
        }
    )

    IMMUTABLE_STATES: frozenset[str] = frozenset(
        {APPROVED, PUSH_IN_PROGRESS, PUSHED, PUSH_FAILED, VOIDED}
    )

    TERMINAL_STATES: frozenset[str] = frozenset({PUSHED, VOIDED})


class EntryType:
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


# INTENTIONAL DESIGN NOTE: accounting_jv_aggregates is a MUTABLE state projection.
# It is intentionally excluded from APPEND_ONLY_TABLES.
# The immutable audit trail lives in accounting_jv_state_events (append-only).
# This table tracks current JV state only - a read-optimised view of the event log.
# Any JV status change MUST also insert a row in accounting_jv_state_events.
# See docs/design/append-only-architecture.md for the full pattern rationale.
class AccountingJVAggregate(FinancialBase):
    __tablename__ = "accounting_jv_aggregates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "jv_number", name="uq_jv_number_per_tenant"),
        UniqueConstraint(
            "tenant_id",
            "external_reference_id",
            name="uq_accounting_jv_external_ref_per_tenant",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    cost_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_cost_centres.id", ondelete="SET NULL"),
        nullable=True,
    )
    jv_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JVStatus.DRAFT)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    external_reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    workflow_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resubmission_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    lines: Mapped[list[AccountingJVLine]] = relationship(
        "AccountingJVLine",
        foreign_keys="AccountingJVLine.jv_id",
        order_by="AccountingJVLine.line_number",
        lazy="selectin",
    )
    state_events: Mapped[list[AccountingJVStateEvent]] = relationship(
        "AccountingJVStateEvent",
        foreign_keys="AccountingJVStateEvent.jv_id",
        order_by="AccountingJVStateEvent.occurred_at",
        lazy="selectin",
    )

    @property
    def is_immutable(self) -> bool:
        return self.status in JVStatus.IMMUTABLE_STATES

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class AccountingJVLine(FinancialBase):
    __tablename__ = "accounting_jv_lines"

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    jv_version: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    transaction_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    functional_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    base_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    cost_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_cost_centres.id", ondelete="SET NULL"),
        nullable=True,
    )
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_tax_line: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class AccountingJVStateEvent(FinancialBase):
    __tablename__ = "accounting_jv_state_events"

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    jv_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_intents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
