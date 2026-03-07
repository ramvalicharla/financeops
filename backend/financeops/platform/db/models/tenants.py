from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenant(FinancialBase):
    __tablename__ = "cp_tenants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tenant_code", name="uq_cp_tenants_code"),
        Index("idx_cp_tenants_tenant_created", "tenant_id", "created_at"),
    )

    tenant_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    billing_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
