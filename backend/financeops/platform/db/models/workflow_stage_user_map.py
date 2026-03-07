from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowStageUserMap(FinancialBase):
    __tablename__ = "cp_workflow_stage_user_map"
    __table_args__ = (
        UniqueConstraint("tenant_id", "stage_id", "user_id", name="uq_cp_workflow_stage_user_map"),
    )

    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_template_stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
