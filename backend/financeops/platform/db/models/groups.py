from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpGroup(FinancialBase):
    __tablename__ = "cp_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "group_code", name="uq_cp_group_code"),
        Index("idx_cp_groups_org", "tenant_id", "organisation_id"),
    )

    group_code: Mapped[str] = mapped_column(String(64), nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
