from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class MisTemplate(FinancialBase):
    """
    MIS Template profile — INSERT ONLY.
    Each structural change creates a new version row (new is_active=True,
    old rows set is_active=False by service layer via new insert).
    """
    __tablename__ = "mis_templates"
    __table_args__ = (
        Index("idx_mis_templates_tenant_created", "tenant_id", "created_at"),
        Index("idx_mis_templates_entity", "tenant_id", "entity_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_master: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON: {sheets: [{name, columns: [{header, data_type}], row_categories: [...]}]}
    template_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sheet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class MisUpload(FinancialBase):
    """
    MIS file upload record — INSERT ONLY.
    One row per upload event. parsed_data contains extracted worksheet content.
    """
    __tablename__ = "mis_uploads"
    __table_args__ = (
        Index("idx_mis_uploads_tenant_created", "tenant_id", "created_at"),
        Index("idx_mis_uploads_period", "tenant_id", "period_year", "period_month"),
    )

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mis_templates.id"), nullable=True
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    # status: pending / processed / error
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    upload_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
