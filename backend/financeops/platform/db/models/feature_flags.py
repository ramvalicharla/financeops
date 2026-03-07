from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpModuleFeatureFlag(FinancialBase):
    __tablename__ = "cp_module_feature_flags"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "module_id",
            "flag_key",
            "target_scope_type",
            "target_scope_id",
            "effective_from",
            name="uq_cp_feature_flag_scope_effective",
        ),
        Index("idx_cp_feature_flags_lookup", "tenant_id", "module_id", "flag_key", "effective_from"),
    )

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_module_registry.id", ondelete="RESTRICT"),
        nullable=False,
    )
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    flag_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rollout_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    compute_enabled: Mapped[bool] = mapped_column(nullable=False)
    write_enabled: Mapped[bool] = mapped_column(nullable=False)
    visibility_enabled: Mapped[bool] = mapped_column(nullable=False)
    target_scope_type: Mapped[str] = mapped_column(String(16), nullable=False, default="tenant")
    target_scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    traffic_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
