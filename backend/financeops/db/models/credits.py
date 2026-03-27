from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase, UUIDBase, utc_now
from decimal import Decimal


class CreditDirection(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class CreditTransactionStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    released = "released"
    failed = "failed"


class ReservationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    released = "released"


class CreditBalance(UUIDBase):
    """
    Current credit balance for a tenant.
    balance = total credits ever added.
    reserved = credits currently reserved (not yet consumed).
    available = balance - reserved (computed at application layer).
    """
    __tablename__ = "credit_balances"
    __table_args__ = (
        Index("idx_credit_balances_tenant", "tenant_id", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=6), nullable=False, default=Decimal("0")
    )
    reserved: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=6), nullable=False, default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    @property
    def available(self) -> Decimal:
        return self.balance - self.reserved


class CreditTransaction(FinancialBase):
    """
    TIER 1 IMMUTABLE: records every credit movement.
    INSERT ONLY — no updates, no deletes.
    """
    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index("idx_credit_tx_tenant_created", "tenant_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=6), nullable=False)
    direction: Mapped[CreditDirection] = mapped_column(
        Enum(CreditDirection, name="credit_direction_enum", native_enum=False),
        nullable=False,
    )
    balance_before: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=6), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=6), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[CreditTransactionStatus] = mapped_column(
        Enum(CreditTransactionStatus, name="credit_tx_status_enum", native_enum=False),
        nullable=False,
        default=CreditTransactionStatus.confirmed,
    )


class CreditReservation(UUIDBase):
    """
    Temporary credit reservation while a task is running.
    Converted to CreditTransaction on confirm or released on failure.
    """
    __tablename__ = "credit_reservations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=6), nullable=False)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum", native_enum=False),
        nullable=False,
        default=ReservationStatus.pending,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
