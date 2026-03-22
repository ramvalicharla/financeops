from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class SecretRotationLog(Base):
    __tablename__ = "secret_rotation_log"
    __table_args__ = (
        CheckConstraint(
            "secret_type IN ('smtp','webhook_signing','erp_api_key')",
            name="ck_secret_rotation_log_secret_type",
        ),
        CheckConstraint(
            "rotation_method IN ('manual','scheduled','emergency')",
            name="ck_secret_rotation_log_rotation_method",
        ),
        CheckConstraint(
            "status IN ('initiated','verified','completed','failed')",
            name="ck_secret_rotation_log_status",
        ),
        CheckConstraint(
            "resource_type IS NULL OR resource_type IN ('delivery_schedule','erp_connector')",
            name="ck_secret_rotation_log_resource_type",
        ),
        Index(
            "idx_secret_rotation_log_tenant_type_initiated_desc",
            "tenant_id",
            "secret_type",
            text("initiated_at DESC"),
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    secret_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rotated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rotation_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'manual'"),
        default="manual",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_secret_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    new_secret_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["SecretRotationLog"]
