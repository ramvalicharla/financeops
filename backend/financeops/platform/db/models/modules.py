from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import UUIDBase


class CpModuleRegistry(UUIDBase):
    __tablename__ = "cp_module_registry"
    __table_args__ = (
        Index("idx_cp_module_registry_engine", "engine_context"),
    )

    module_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    module_name: Mapped[str] = mapped_column(String(255), nullable=False)
    engine_context: Mapped[str] = mapped_column(String(64), nullable=False)
    is_financial_impacting: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
