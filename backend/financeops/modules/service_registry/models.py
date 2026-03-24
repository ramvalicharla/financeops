from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ModuleRegistry(Base):
    __tablename__ = "module_registry"
    __table_args__ = (
        CheckConstraint(
            "health_status IN ('healthy','degraded','unhealthy','unknown')",
            name="ck_module_registry_health_status",
        ),
        Index("idx_module_registry_module_name", "module_name"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    module_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    module_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'1.0.0'"),
        default="1.0.0",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )
    health_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'unknown'"),
        default="unknown",
    )
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    route_prefix: Mapped[str | None] = mapped_column(String(100), nullable=True)
    depends_on: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class TaskRegistry(Base):
    __tablename__ = "task_registry"
    __table_args__ = (
        CheckConstraint(
            "queue_name IN ('file_scan','parse','erp_sync','report_gen','email','ai_inference','notification','default')",
            name="ck_task_registry_queue_name",
        ),
        CheckConstraint(
            "last_run_status IN ('success','failure','timeout') OR last_run_status IS NULL",
            name="ck_task_registry_last_run_status",
        ),
        Index("idx_task_registry_task_name", "task_name"),
        Index("idx_task_registry_queue_name", "queue_name"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    task_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avg_duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    success_rate_7d: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_scheduled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["ModuleRegistry", "TaskRegistry"]

