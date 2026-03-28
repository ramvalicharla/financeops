from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class EmailProcessingStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    ALL = frozenset({PENDING, PROCESSING, PROCESSED, REJECTED, FAILED})


class PortalSubmissionStatus:
    RECEIVED = "RECEIVED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ALL = frozenset({RECEIVED, UNDER_REVIEW, ACCEPTED, REJECTED})


class AccountingInboundEmailMessage(FinancialBase):
    __tablename__ = "accounting_inbound_email_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "message_id", name="uq_inbound_email_message_id"),
        Index("ix_inbound_email_sender", "tenant_id", "sender_email"),
        Index("ix_inbound_email_status", "tenant_id", "processing_status"),
        CheckConstraint(
            "processing_status IN ('PENDING','PROCESSING','PROCESSED','REJECTED','FAILED')",
            name="ck_accounting_inbound_email_messages_processing_status",
        ),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(512), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(256), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_whitelisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmailProcessingStatus.PENDING,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_reply_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VendorPortalSubmission(FinancialBase):
    __tablename__ = "vendor_portal_submissions"
    __table_args__ = (
        UniqueConstraint("reference_id", name="uq_vendor_portal_submissions_reference_id"),
        Index("ix_vendor_portal_submissions_status", "tenant_id", "status"),
        Index("ix_vendor_portal_submissions_submitter_email", "tenant_id", "submitter_email"),
        CheckConstraint(
            "status IN ('RECEIVED','UNDER_REVIEW','ACCEPTED','REJECTED')",
            name="ck_vendor_portal_submissions_status",
        ),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reference_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    submitter_email: Mapped[str] = mapped_column(String(256), nullable=False)
    submitter_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    vendor_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    r2_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scan_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PortalSubmissionStatus.RECEIVED,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
