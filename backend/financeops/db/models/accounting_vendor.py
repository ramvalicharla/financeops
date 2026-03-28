from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from financeops.db.base import FinancialBase


class TDSSection:
    S194C = "194C"
    S194J = "194J"
    S194I = "194I"
    ALL = frozenset({S194C, S194J, S194I})


class DocumentType:
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    CONTRACT = "CONTRACT"
    OTHER = "OTHER"


class ScanStatus:
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    PENDING = "PENDING"


class DuplicateAction:
    FLAGGED = "FLAGGED"
    SKIPPED = "SKIPPED"
    OVERRIDDEN = "OVERRIDDEN"
    RELATED = "RELATED"


class AccountingVendor(FinancialBase):
    __tablename__ = "accounting_vendors"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str] = mapped_column(String(256), nullable=False)
    vendor_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tds_section: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tds_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    tds_threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erp_vendor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    erp_connector_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    attachments: Mapped[list["AccountingAttachment"]] = relationship(
        "AccountingAttachment",
        foreign_keys="AccountingAttachment.vendor_id",
        lazy="selectin",
    )


class AccountingAttachment(FinancialBase):
    __tablename__ = "accounting_attachments"

    jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    r2_bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    worm_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    worm_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    scan_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    erp_links: Mapped[list["ErpAttachmentLink"]] = relationship(
        "ErpAttachmentLink",
        foreign_keys="ErpAttachmentLink.attachment_id",
        lazy="selectin",
    )
    duplicate_flags: Mapped[list["AccountingDuplicateFingerprint"]] = relationship(
        "AccountingDuplicateFingerprint",
        foreign_keys="AccountingDuplicateFingerprint.attachment_id",
        lazy="selectin",
    )


class ErpAttachmentLink(FinancialBase):
    __tablename__ = "erp_attachment_links"

    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_attachments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_document_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    erp_journal_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    push_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountingDuplicateFingerprint(FinancialBase):
    __tablename__ = "accounting_duplicate_fingerprints"

    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_attachments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
        nullable=True,
    )
    detection_layer: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    layer2_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount_bucket: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    date_bucket: Mapped[date | None] = mapped_column(Date, nullable=True)
    layer3_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflict_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    conflict_jv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_jv_aggregates.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False, default=DuplicateAction.FLAGGED)
    action_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
