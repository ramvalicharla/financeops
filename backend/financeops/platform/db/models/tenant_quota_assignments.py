from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantQuotaAssignment(FinancialBase):
    __tablename__ = "cp_tenant_quota_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "quota_type", "effective_from", name="uq_cp_tenant_quota_effective"),
        Index("idx_cp_tenant_quota_assignment", "tenant_id", "quota_type", "effective_from"),
    )

    quota_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_quota_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    quota_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_type: Mapped[str] = mapped_column(String(16), nullable=False)
    window_seconds: Mapped[int] = mapped_column(nullable=False)
    max_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enforcement_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
