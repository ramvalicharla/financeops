from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import UUIDBase


class CpPackage(UUIDBase):
    __tablename__ = "cp_packages"
    __table_args__ = (
        Index("idx_cp_packages_code", "package_code"),
    )

    package_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
