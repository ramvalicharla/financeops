from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class OnboardingState(Base):
    __tablename__ = "onboarding_state"
    __table_args__ = (
        CheckConstraint("current_step >= 1 AND current_step <= 5", name="ck_onboarding_state_current_step"),
        CheckConstraint(
            "industry IS NULL OR industry IN ('saas','manufacturing','retail','professional_services','healthcare','general','it_services')",
            name="ck_onboarding_state_industry",
        ),
        UniqueConstraint("tenant_id", name="uq_onboarding_state_tenant_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    template_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    erp_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
