from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.platform.db.models.workflow_template_versions import CpWorkflowTemplateVersion
from financeops.platform.db.models.workflow_templates import (
    CpWorkflowStageRoleMap,
    CpWorkflowTemplate,
    CpWorkflowTemplateStage,
)
from financeops.platform.db.models.workflow_stage_user_map import CpWorkflowStageUserMap
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_code: str,
    module_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpWorkflowTemplate:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpWorkflowTemplate,
        tenant_id=tenant_id,
        record_data={"template_code": template_code, "module_id": str(module_id)},
        values={
            "template_code": template_code,
            "module_id": module_id,
            "is_active": True,
            "created_by": actor_user_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.workflow.template.created",
            resource_type="cp_workflow_template",
            new_value={"template_code": template_code, "correlation_id": correlation_id},
        ),
    )


async def create_template_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    version_no: int,
    effective_from: datetime,
    effective_to: datetime | None,
    stages: list[dict[str, object]],
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpWorkflowTemplateVersion:
    existing_template = await session.execute(
        select(CpWorkflowTemplate.id).where(
            CpWorkflowTemplate.tenant_id == tenant_id,
            CpWorkflowTemplate.id == template_id,
        )
    )
    if existing_template.scalar_one_or_none() is None:
        raise NotFoundError("Workflow template not found")

    version = await AuditWriter.insert_financial_record(
        session,
        model_class=CpWorkflowTemplateVersion,
        tenant_id=tenant_id,
        record_data={
            "template_id": str(template_id),
            "version_no": version_no,
            "effective_from": effective_from.isoformat(),
        },
        values={
            "template_id": template_id,
            "version_no": version_no,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "is_active": True,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.workflow.template_version.created",
            resource_type="cp_workflow_template_version",
            new_value={"template_id": str(template_id), "version_no": version_no, "correlation_id": correlation_id},
        ),
    )

    seen_orders: set[int] = set()
    for stage in stages:
        stage_order = int(stage["stage_order"])
        if stage_order in seen_orders:
            raise ValidationError("Duplicate stage_order in template version")
        seen_orders.add(stage_order)

        created_stage = await AuditWriter.insert_financial_record(
            session,
            model_class=CpWorkflowTemplateStage,
            tenant_id=tenant_id,
            record_data={
                "template_version_id": str(version.id),
                "stage_order": stage_order,
                "stage_code": str(stage["stage_code"]),
            },
            values={
                "template_version_id": version.id,
                "stage_order": stage_order,
                "stage_code": str(stage["stage_code"]),
                "stage_type": str(stage["stage_type"]),
                "approval_mode": str(stage["approval_mode"]),
                "threshold_type": str(stage["threshold_type"]),
                "threshold_value": stage.get("threshold_value"),
                "sla_hours": stage.get("sla_hours"),
                "escalation_target_role_id": stage.get("escalation_target_role_id"),
                "is_terminal": bool(stage.get("is_terminal", False)),
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="platform.workflow.template_stage.created",
                resource_type="cp_workflow_template_stage",
                new_value={"stage_order": stage_order, "stage_code": str(stage["stage_code"])},
            ),
        )

        for role_id in list(stage.get("role_ids", [])):
            await AuditWriter.insert_financial_record(
                session,
                model_class=CpWorkflowStageRoleMap,
                tenant_id=tenant_id,
                record_data={"stage_id": str(created_stage.id), "role_id": str(role_id)},
                values={"stage_id": created_stage.id, "role_id": uuid.UUID(str(role_id))},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=actor_user_id,
                    action="platform.workflow.template_stage.role_mapped",
                    resource_type="cp_workflow_stage_role_map",
                    new_value={"stage_id": str(created_stage.id), "role_id": str(role_id)},
                ),
            )

        for user_id in list(stage.get("user_ids", [])):
            await AuditWriter.insert_financial_record(
                session,
                model_class=CpWorkflowStageUserMap,
                tenant_id=tenant_id,
                record_data={"stage_id": str(created_stage.id), "user_id": str(user_id)},
                values={"stage_id": created_stage.id, "user_id": uuid.UUID(str(user_id))},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=actor_user_id,
                    action="platform.workflow.template_stage.user_mapped",
                    resource_type="cp_workflow_stage_user_map",
                    new_value={"stage_id": str(created_stage.id), "user_id": str(user_id)},
                ),
            )

    return version


async def resolve_active_template_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    as_of: datetime | None = None,
) -> CpWorkflowTemplateVersion:
    check_time = as_of or _now()
    result = await session.execute(
        select(CpWorkflowTemplateVersion)
        .where(
            CpWorkflowTemplateVersion.tenant_id == tenant_id,
            CpWorkflowTemplateVersion.template_id == template_id,
            CpWorkflowTemplateVersion.effective_from <= check_time,
            (CpWorkflowTemplateVersion.effective_to.is_(None) | (CpWorkflowTemplateVersion.effective_to > check_time)),
            CpWorkflowTemplateVersion.is_active.is_(True),
        )
        .order_by(CpWorkflowTemplateVersion.version_no.desc())
    )
    version = result.scalars().first()
    if version is None:
        raise NotFoundError("No active workflow template version")
    return version
