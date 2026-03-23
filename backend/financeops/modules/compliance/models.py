from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class ComplianceControl(Base):
    __tablename__ = "compliance_controls"
    __table_args__ = (
        CheckConstraint(
            "framework IN ('SOC2','ISO27001','GDPR')",
            name="ck_compliance_controls_framework",
        ),
        CheckConstraint(
            "status IN ('not_evaluated','pass','fail','partial','not_applicable')",
            name="ck_compliance_controls_status",
        ),
        CheckConstraint(
            "rag_status IN ('green','amber','red','grey')",
            name="ck_compliance_controls_rag_status",
        ),
        Index(
            "idx_compliance_controls_tenant_framework_category",
            "tenant_id",
            "framework",
            "category",
        ),
        UniqueConstraint(
            "tenant_id",
            "framework",
            "control_id",
            name="uq_compliance_controls_tenant_framework_control",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    framework: Mapped[str] = mapped_column(String(20), nullable=False)
    control_id: Mapped[str] = mapped_column(String(30), nullable=False)
    control_name: Mapped[str] = mapped_column(String(300), nullable=False)
    control_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_evaluated",
        server_default=text("'not_evaluated'"),
    )
    rag_status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="grey",
        server_default=text("'grey'"),
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_evaluation_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_evaluable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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


class ComplianceEvent(Base):
    __tablename__ = "compliance_events"
    __table_args__ = (
        CheckConstraint(
            "framework IN ('SOC2','ISO27001','GDPR')",
            name="ck_compliance_events_framework",
        ),
        CheckConstraint(
            "event_type IN ('auto_pass','auto_fail','manual_pass','manual_fail','evidence_added','status_changed','evaluation_run')",
            name="ck_compliance_events_event_type",
        ),
        CheckConstraint(
            "new_status IN ('not_evaluated','pass','fail','partial','not_applicable')",
            name="ck_compliance_events_new_status",
        ),
        Index(
            "idx_compliance_events_tenant_framework_control_created",
            "tenant_id",
            "framework",
            "control_id",
            text("created_at DESC"),
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    framework: Mapped[str] = mapped_column(String(20), nullable=False)
    control_id: Mapped[str] = mapped_column(String(30), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_snapshot: Mapped[dict[str, str] | list[dict[str, str]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class UserPiiKey(Base):
    __tablename__ = "user_pii_keys"
    __table_args__ = (
        Index("idx_user_pii_keys_tenant_user", "tenant_id", "user_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    encrypted_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ErasureLog(Base):
    __tablename__ = "erasure_log"
    __table_args__ = (
        CheckConstraint(
            "request_method IN ('self','admin','regulatory')",
            name="ck_erasure_log_request_method",
        ),
        CheckConstraint(
            "status IN ('initiated','completed','failed')",
            name="ck_erasure_log_status",
        ),
        Index("idx_erasure_log_tenant_created", "tenant_id", text("created_at DESC")),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    pii_fields_erased: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = [
    "ComplianceControl",
    "ComplianceEvent",
    "ErasureLog",
    "UserPiiKey",
]
