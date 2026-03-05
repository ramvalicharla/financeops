from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class AuditTrail(FinancialBase):
    """
    TIER 1: IMMUTABLE EVIDENTIARY — INSERT ONLY.
    Every significant action in the platform is recorded here.
    chain_hash links each entry to the previous for tamper detection.
    """
    __tablename__ = "audit_trail"
    __table_args__ = (
        Index("idx_audit_trail_tenant_created", "tenant_id", "created_at"),
        Index("idx_audit_trail_resource", "tenant_id", "resource_type", "resource_id"),
        {"comment": "TIER 1: IMMUTABLE EVIDENTIARY — INSERT ONLY"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_value_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_value_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
