from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class DeliverySchedule(Base):
    __tablename__ = "delivery_schedules"
    __table_args__ = (
        CheckConstraint(
            "schedule_type IN ('BOARD_PACK','REPORT')",
            name="ck_delivery_schedules_schedule_type",
        ),
        CheckConstraint(
            "export_format IN ('PDF','EXCEL','CSV')",
            name="ck_delivery_schedules_export_format",
        ),
        Index(
            "idx_delivery_schedules_tenant_active",
            "tenant_id",
            "is_active",
        ),
        Index(
            "idx_delivery_schedules_tenant_next_run_at",
            "tenant_id",
            "next_run_at",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_definition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default=text("'UTC'"),
        default="UTC",
    )
    recipients: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    export_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'PDF'"),
        default="PDF",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
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


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','DELIVERED','FAILED')",
            name="ck_delivery_logs_status",
        ),
        CheckConstraint(
            "channel_type IN ('EMAIL','WEBHOOK')",
            name="ck_delivery_logs_channel_type",
        ),
        Index(
            "idx_delivery_logs_schedule_triggered_desc",
            "schedule_id",
            text("triggered_at DESC"),
        ),
        Index(
            "idx_delivery_logs_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "idx_delivery_logs_tenant_idempotency_key",
            "tenant_id",
            "idempotency_key",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_schedules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'PENDING'"),
        default="PENDING",
    )
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
