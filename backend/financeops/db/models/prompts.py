from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import UUIDBase, utc_now


class AiPromptVersion(UUIDBase):
    """
    Versioned AI prompt store. Active prompts are loaded at runtime.
    Only one version per prompt_key may be active at a time.
    Deactivation is done by setting is_active=False and recording deactivated_at.
    """
    __tablename__ = "ai_prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_prompt_key_version"),
    )

    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_target: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    performance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acceptance_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
