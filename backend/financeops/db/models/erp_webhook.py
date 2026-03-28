from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CanonicalWebhookEventType:
    PAYMENT_RECEIVED = "payment_received"
    INVOICE_UPDATED = "invoice_updated"
    INVOICE_CREATED = "invoice_created"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    VENDOR_CREATED = "vendor_created"
    VENDOR_UPDATED = "vendor_updated"
    JOURNAL_CREATED = "journal_created"
    JOURNAL_UPDATED = "journal_updated"
    UNKNOWN = "unknown"

    ALL = frozenset(
        {
            PAYMENT_RECEIVED,
            INVOICE_UPDATED,
            INVOICE_CREATED,
            ACCOUNT_CREATED,
            ACCOUNT_UPDATED,
            VENDOR_CREATED,
            VENDOR_UPDATED,
            JOURNAL_CREATED,
            JOURNAL_UPDATED,
            UNKNOWN,
        }
    )


class ErpWebhookEvent(FinancialBase):
    __tablename__ = "erp_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "connector_type",
            "message_id",
            name="uq_erp_webhook_events_message_id",
        ),
        Index("ix_erp_webhook_events_connector_type", "tenant_id", "connector_type"),
        Index("ix_erp_webhook_events_processed", "tenant_id", "processed", "received_at"),
        Index("ix_erp_webhook_events_canonical_type", "tenant_id", "canonical_event_type"),
        Index(
            "ix_erp_webhook_events_dead_lettered",
            "tenant_id",
            "dead_lettered",
            postgresql_where=text("dead_lettered = true"),
        ),
    )

    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dead_lettered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dead_letter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
