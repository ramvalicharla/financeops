from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowStageEvent(FinancialBase):
    __tablename__ = "cp_workflow_stage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "stage_instance_id", "event_seq", name="uq_cp_workflow_stage_event_seq"),
        UniqueConstraint(
            "tenant_id",
            "stage_instance_id",
            "event_type",
            "idempotency_key",
            name="uq_cp_workflow_stage_event_idempotent",
        ),
        Index("idx_cp_workflow_stage_events", "tenant_id", "stage_instance_id", "event_seq"),
    )

    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_stage_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
