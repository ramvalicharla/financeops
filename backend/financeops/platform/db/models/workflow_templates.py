from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase


class CpWorkflowTemplate(FinancialBase):
    __tablename__ = "cp_workflow_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_code", name="uq_cp_workflow_template_code"),
        Index("idx_cp_workflow_templates_module", "tenant_id", "module_id"),
    )

    template_code: Mapped[str] = mapped_column(String(128), nullable=False)
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_module_registry.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class CpWorkflowTemplateStage(FinancialBase):
    __tablename__ = "cp_workflow_template_stages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "template_version_id",
            "stage_order",
            name="uq_cp_workflow_stage_order",
        ),
        Index("idx_cp_workflow_template_stages_version", "tenant_id", "template_version_id"),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_code: Mapped[str] = mapped_column(String(128), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold_type: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_target_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_terminal: Mapped[bool] = mapped_column(nullable=False, default=False)


class CpWorkflowStageRoleMap(FinancialBase):
    __tablename__ = "cp_workflow_stage_role_map"
    __table_args__ = (
        UniqueConstraint("tenant_id", "stage_id", "role_id", name="uq_cp_stage_role_map"),
    )

    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_workflow_template_stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cp_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
