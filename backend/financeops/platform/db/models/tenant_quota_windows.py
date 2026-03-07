from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantQuotaWindow(FinancialBase):
    __tablename__ = "cp_tenant_quota_windows"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "quota_type",
            "window_start",
            "window_end",
            name="uq_cp_quota_window_unique",
        ),
        Index("idx_cp_quota_window_lookup", "tenant_id", "quota_type", "window_end"),
    )

    quota_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_tenant_quota_usage_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
