from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowInstance(FinancialBase):
    __tablename__ = "cp_workflow_instances"
    __table_args__ = (
        Index("idx_cp_workflow_instances_tenant_created", "tenant_id", "created_at"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_module_registry.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CpWorkflowStageInstance(FinancialBase):
    __tablename__ = "cp_workflow_stage_instances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workflow_instance_id",
            "template_stage_id",
            name="uq_cp_workflow_stage_instance",
        ),
        Index("idx_cp_workflow_stage_instances", "tenant_id", "workflow_instance_id"),
    )

    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_template_stages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stage_order: Mapped[int] = mapped_column(nullable=False)
    stage_code: Mapped[str] = mapped_column(String(128), nullable=False)
