from __future__ import annotations

import uuid

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.platform.db.models.workflow_instances import CpWorkflowInstance, CpWorkflowStageInstance
from financeops.platform.db.models.workflow_templates import CpWorkflowTemplateStage
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.platform.services.workflows.event_service import append_stage_event, append_workflow_event, derive_workflow_status


async def create_workflow_instance(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    template_version_id: uuid.UUID,
    module_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    initiated_by: uuid.UUID,
    correlation_id: str,
) -> CpWorkflowInstance:
    instance = await AuditWriter.insert_financial_record(
        session,
        model_class=CpWorkflowInstance,
        tenant_id=tenant_id,
        record_data={
            "template_id": str(template_id),
            "template_version_id": str(template_version_id),
            "resource_id": str(resource_id),
        },
        values={
            "template_id": template_id,
            "template_version_id": template_version_id,
            "module_id": module_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "initiated_by": initiated_by,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="platform.workflow.instance.created",
            resource_type="cp_workflow_instance",
            new_value={"template_id": str(template_id), "resource_id": str(resource_id)},
        ),
    )

    stages_result = await session.execute(
        select(CpWorkflowTemplateStage)
        .where(
            CpWorkflowTemplateStage.tenant_id == tenant_id,
            CpWorkflowTemplateStage.template_version_id == template_version_id,
        )
        .order_by(asc(CpWorkflowTemplateStage.stage_order))
    )
    stages = list(stages_result.scalars().all())
    if not stages:
        raise NotFoundError("No stages found for workflow template version")

    first_stage_id: uuid.UUID | None = None
    for stage in stages:
        stage_instance = await AuditWriter.insert_financial_record(
            session,
            model_class=CpWorkflowStageInstance,
            tenant_id=tenant_id,
            record_data={"workflow_instance_id": str(instance.id), "template_stage_id": str(stage.id)},
            values={
                "workflow_instance_id": instance.id,
                "template_stage_id": stage.id,
                "stage_order": stage.stage_order,
                "stage_code": stage.stage_code,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=initiated_by,
                action="platform.workflow.stage_instance.created",
                resource_type="cp_workflow_stage_instance",
                new_value={"workflow_instance_id": str(instance.id), "stage_code": stage.stage_code},
            ),
        )
        await append_stage_event(
            session,
            tenant_id=tenant_id,
            stage_instance_id=stage_instance.id,
            event_type="stage_pending",
            idempotency_key="stage-created",
            metadata_json={"stage_order": stage.stage_order},
            actor_user_id=initiated_by,
            correlation_id=correlation_id,
        )
        if first_stage_id is None:
            first_stage_id = stage_instance.id

    await append_workflow_event(
        session,
        tenant_id=tenant_id,
        workflow_instance_id=instance.id,
        event_type="instance_created",
        idempotency_key="instance-created",
        metadata_json={"template_version_id": str(template_version_id)},
        actor_user_id=initiated_by,
        correlation_id=correlation_id,
    )
    await append_workflow_event(
        session,
        tenant_id=tenant_id,
        workflow_instance_id=instance.id,
        event_type="instance_running",
        idempotency_key="instance-running",
        metadata_json={},
        actor_user_id=initiated_by,
        correlation_id=correlation_id,
    )
    if first_stage_id is not None:
        await append_stage_event(
            session,
            tenant_id=tenant_id,
            stage_instance_id=first_stage_id,
            event_type="stage_running",
            idempotency_key="stage-running-initial",
            metadata_json={},
            actor_user_id=initiated_by,
            correlation_id=correlation_id,
        )
    return instance


async def get_workflow_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
) -> dict:
    return await derive_workflow_status(
        session,
        tenant_id=tenant_id,
        workflow_instance_id=workflow_instance_id,
    )
