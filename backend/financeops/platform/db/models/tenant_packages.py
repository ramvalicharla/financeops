from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpTenantPackageAssignment(FinancialBase):
    __tablename__ = "cp_tenant_package_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "package_id", "effective_from", name="uq_cp_tenant_package_effective"),
        Index("idx_cp_tenant_package_status", "tenant_id", "assignment_status", "effective_from"),
    )

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_packages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
