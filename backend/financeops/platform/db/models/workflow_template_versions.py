from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowTemplateVersion(FinancialBase):
    __tablename__ = "cp_workflow_template_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", "version_no", name="uq_cp_workflow_template_version"),
        UniqueConstraint("tenant_id", "template_id", "effective_from", name="uq_cp_workflow_template_effective"),
        Index("idx_cp_workflow_template_versions", "tenant_id", "template_id", "effective_from"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
