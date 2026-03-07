from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantMigrationEvent(FinancialBase):
    __tablename__ = "cp_tenant_migration_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "route_version", "event_seq", name="uq_cp_tenant_migration_seq"),
        UniqueConstraint(
            "tenant_id",
            "route_version",
            "event_type",
            "idempotency_key",
            name="uq_cp_tenant_migration_idempotent",
        ),
        Index("idx_cp_tenant_migration_events", "tenant_id", "route_version", "event_seq"),
    )

    isolation_policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    route_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
