from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantIsolationPolicy(FinancialBase):
    __tablename__ = "cp_tenant_isolation_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "route_version", name="uq_cp_isolation_route_version"),
        UniqueConstraint("tenant_id", "effective_from", name="uq_cp_isolation_effective"),
        Index("idx_cp_isolation_lookup", "tenant_id", "migration_state", "route_version"),
    )

    isolation_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    db_cluster: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), nullable=False)
    worker_pool: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    migration_state: Mapped[str] = mapped_column(String(32), nullable=False)
    route_version: Mapped[int] = mapped_column(nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
