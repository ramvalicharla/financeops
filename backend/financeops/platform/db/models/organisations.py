from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpOrganisation(FinancialBase):
    __tablename__ = "cp_organisations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "organisation_code", "created_at", name="uq_cp_org_code_created"),
        Index("idx_cp_org_tenant_parent", "tenant_id", "parent_organisation_id"),
    )

    organisation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    organisation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_organisations.id", ondelete="SET NULL"),
        nullable=True,
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_organisations.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
