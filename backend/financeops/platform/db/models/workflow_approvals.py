from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowApproval(FinancialBase):
    __tablename__ = "cp_workflow_approvals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "stage_instance_id",
            "acted_by",
            "idempotency_key",
            name="uq_cp_workflow_approval_idempotent",
        ),
        UniqueConstraint(
            "tenant_id",
            "stage_instance_id",
            "request_fingerprint",
            name="uq_cp_workflow_approval_fingerprint",
        ),
        Index("idx_cp_workflow_approvals_stage", "tenant_id", "stage_instance_id", "acted_at"),
    )

    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_stage_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    acted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delegated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
