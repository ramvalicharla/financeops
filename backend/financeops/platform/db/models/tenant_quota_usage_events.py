from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantQuotaUsageEvent(FinancialBase):
    __tablename__ = "cp_tenant_quota_usage_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "quota_type",
            "operation_id",
            "idempotency_key",
            name="uq_cp_quota_usage_idempotent",
        ),
        UniqueConstraint(
            "tenant_id",
            "quota_type",
            "request_fingerprint",
            "window_start",
            "window_end",
            name="uq_cp_quota_usage_fingerprint_window",
        ),
        Index("idx_cp_quota_usage_window", "tenant_id", "quota_type", "window_start", "window_end"),
    )

    quota_type: Mapped[str] = mapped_column(String(64), nullable=False)
    usage_delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    source_layer: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
