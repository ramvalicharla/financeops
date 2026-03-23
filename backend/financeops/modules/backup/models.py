from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class BackupRunLog(Base):
    __tablename__ = "backup_run_log"
    __table_args__ = (
        CheckConstraint(
            "backup_type IN ('full','incremental','wal','redis','r2_sync')",
            name="ck_backup_run_log_type",
        ),
        CheckConstraint(
            "status IN ('started','completed','failed','verified')",
            name="ck_backup_run_log_status",
        ),
        CheckConstraint(
            "triggered_by IN ('scheduled','manual','ci_pipeline')",
            name="ck_backup_run_log_triggered_by",
        ),
        Index("idx_backup_run_log_type_started", "backup_type", text("started_at DESC")),
        Index("idx_backup_run_log_status_created", "status", text("created_at DESC")),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    backup_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    backup_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    retention_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default=text("30"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["BackupRunLog"]
