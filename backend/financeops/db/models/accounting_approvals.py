from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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

from financeops.db.base import FinancialBase, UUIDBase


class ApprovalDecision:
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccountingJVApproval(FinancialBase):
    __tablename__ = "accounting_jv_approvals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "jv_id",
            "acted_by",
            "idempotency_key",
            name="uq_jv_approval_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "jv_id",
            "request_fingerprint",
            name="uq_jv_approval_fingerprint",
        ),
    )

    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    jv_version: Mapped[int] = mapped_column(Integer, nullable=False)
    acted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    delegated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    jv: Mapped["AccountingJVAggregate"] = relationship(
        "AccountingJVAggregate",
        foreign_keys=[jv_id],
        lazy="raise",
    )


class ApprovalSLATimer(UUIDBase):
    __tablename__ = "approval_sla_timers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    jv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    review_sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    approval_sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    review_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nudge_24h_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nudge_48h_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
