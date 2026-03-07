from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import UUIDBase


class CpPermission(UUIDBase):
    __tablename__ = "cp_permissions"
    __table_args__ = (
        Index("idx_cp_permissions_resource_action", "resource_type", "action"),
    )

    permission_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
