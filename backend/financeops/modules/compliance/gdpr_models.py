from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import Base


class GDPRConsentRecord(Base):
    __tablename__ = "gdpr_consent_records"
    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('analytics','marketing','ai_processing','data_sharing','performance_monitoring')",
            name="ck_gdpr_consent_type",
        ),
        CheckConstraint(
            "lawful_basis IN ('consent','legitimate_interest','contract','legal_obligation')",
            name="ck_gdpr_lawful_basis",
        ),
        Index("idx_gdpr_consent_tenant_user_type", "tenant_id", "user_id", "consent_type"),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "consent_type",
            name="uq_gdpr_consent_tenant_user_type",
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lawful_basis: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="consent",
        server_default=text("'consent'"),
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


class GDPRDataRequest(Base):
    __tablename__ = "gdpr_data_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('portability','erasure','access','rectification','restriction','objection')",
            name="ck_gdpr_data_request_type",
        ),
        CheckConstraint(
            "status IN ('received','processing','completed','rejected')",
            name="ck_gdpr_data_request_status",
        ),
        Index("idx_gdpr_data_requests_tenant_user_created", "tenant_id", "user_id", text("created_at DESC")),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="received",
        server_default=text("'received'"),
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class GDPRBreachRecord(Base):
    __tablename__ = "gdpr_breach_records"
    __table_args__ = (
        CheckConstraint(
            "breach_type IN ('unauthorized_access','data_loss','ransomware','accidental_disclosure','other')",
            name="ck_gdpr_breach_type",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="ck_gdpr_breach_severity",
        ),
        CheckConstraint(
            "status IN ('open','reported','closed')",
            name="ck_gdpr_breach_status",
        ),
        Index("idx_gdpr_breach_tenant_discovered", "tenant_id", text("discovered_at DESC")),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_user_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    affected_data_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_to_dpa_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_users_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        server_default=text("'open'"),
    )
    remediation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


__all__ = ["GDPRBreachRecord", "GDPRConsentRecord", "GDPRDataRequest"]
