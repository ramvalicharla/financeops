from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpRole(FinancialBase):
    __tablename__ = "cp_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", name="uq_cp_roles_code"),
        Index("idx_cp_roles_scope", "tenant_id", "role_scope", "is_active"),
    )

    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    role_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    inherits_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
