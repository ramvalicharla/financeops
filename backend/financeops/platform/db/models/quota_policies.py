from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import UUIDBase


class CpQuotaPolicy(UUIDBase):
    __tablename__ = "cp_quota_policies"
    __table_args__ = (
        UniqueConstraint("quota_type", "window_type", name="uq_cp_quota_policy_type_window"),
        Index("idx_cp_quota_policy_type", "quota_type"),
    )

    quota_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_type: Mapped[str] = mapped_column(String(16), nullable=False)
    window_seconds: Mapped[int] = mapped_column(nullable=False)
    default_max_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    default_enforcement_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
