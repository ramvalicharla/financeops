from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import asc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.platform.db.models.workflow_approvals import CpWorkflowApproval
from financeops.platform.db.models.workflow_instances import CpWorkflowStageInstance
from financeops.platform.db.models.workflow_stage_user_map import CpWorkflowStageUserMap
from financeops.platform.db.models.workflow_templates import CpWorkflowTemplateStage
from financeops.platform.db.models.workflow_templates import CpWorkflowStageRoleMap
from financeops.platform.db.models.user_role_assignments import CpUserRoleAssignment
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.platform.services.workflows.event_service import append_stage_event, append_workflow_event


async def _get_stage_with_config(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stage_instance_id: uuid.UUID,
) -> tuple[CpWorkflowStageInstance, CpWorkflowTemplateStage]:
    stage_result = await session.execute(
        select(CpWorkflowStageInstance).where(
            CpWorkflowStageInstance.tenant_id == tenant_id,
            CpWorkflowStageInstance.id == stage_instance_id,
        )
    )
    stage_instance = stage_result.scalar_one_or_none()
    if stage_instance is None:
        raise NotFoundError("Stage instance not found")

    config_result = await session.execute(
        select(CpWorkflowTemplateStage).where(
            CpWorkflowTemplateStage.tenant_id == tenant_id,
            CpWorkflowTemplateStage.id == stage_instance.template_stage_id,
        )
    )
    stage_config = config_result.scalar_one_or_none()
    if stage_config is None:
        raise NotFoundError("Template stage not found")
    return stage_instance, stage_config


async def _get_next_stage_instance(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
    current_stage_order: int,
) -> CpWorkflowStageInstance | None:
    result = await session.execute(
        select(CpWorkflowStageInstance)
        .where(
            CpWorkflowStageInstance.tenant_id == tenant_id,
            CpWorkflowStageInstance.workflow_instance_id == workflow_instance_id,
            CpWorkflowStageInstance.stage_order > current_stage_order,
        )
        .order_by(asc(CpWorkflowStageInstance.stage_order))
        .limit(1)
    )
    return result.scalars().first()


async def _expected_actor_count(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stage_config: CpWorkflowTemplateStage,
) -> int:
    user_result = await session.execute(
        select(CpWorkflowStageUserMap.user_id).where(
            CpWorkflowStageUserMap.tenant_id == tenant_id,
            CpWorkflowStageUserMap.stage_id == stage_config.id,
        )
    )
    expected_users = {user_id for user_id in user_result.scalars().all()}

    role_result = await session.execute(
        select(CpWorkflowStageRoleMap.role_id).where(
            CpWorkflowStageRoleMap.tenant_id == tenant_id,
            CpWorkflowStageRoleMap.stage_id == stage_config.id,
        )
    )
    role_ids = {role_id for role_id in role_result.scalars().all()}
    if role_ids:
        assignment_result = await session.execute(
            select(CpUserRoleAssignment.user_id).where(
                CpUserRoleAssignment.tenant_id == tenant_id,
                CpUserRoleAssignment.role_id.in_(role_ids),
                CpUserRoleAssignment.is_active.is_(True),
            )
        )
        expected_users.update(assignment_result.scalars().all())
    return len(expected_users)


def _evaluate_threshold(
    *,
    threshold_type: str,
    threshold_value: int | None,
    approve_count: int,
    reject_count: int,
    distinct_actor_count: int,
    required_approval_count: int,
) -> str | None:
    if threshold_type == "all":
        if reject_count > 0:
            return "rejected"
        required_count = max(1, required_approval_count)
        if approve_count >= required_count and distinct_actor_count >= required_count:
            return "approved"
        return None
    if threshold_type == "any":
        if approve_count > 0:
            return "approved"
        if reject_count > 0:
            return "rejected"
        return None
    if threshold_type == "count":
        if threshold_value is None:
            raise ValidationError("threshold_value is required for count threshold")
        if approve_count >= threshold_value:
            return "approved"
        if reject_count >= threshold_value:
            return "rejected"
        return None
    raise ValidationError("Unknown threshold_type")


async def submit_approval(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    stage_instance_id: uuid.UUID,
    acted_by: uuid.UUID,
    decision: str,
    decision_reason: str | None,
    delegated_from: uuid.UUID | None,
    idempotency_key: str,
    request_fingerprint: str,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> dict:
    stage_instance, stage_config = await _get_stage_with_config(
        session,
        tenant_id=tenant_id,
        stage_instance_id=stage_instance_id,
    )

    try:
        # Keep idempotent insert collisions isolated to a SAVEPOINT so the
        # outer unit of work remains usable for existing-record lookup/events.
        async with session.begin_nested():
            approval = await AuditWriter.insert_financial_record(
                session,
                model_class=CpWorkflowApproval,
                tenant_id=tenant_id,
                record_data={
                    "stage_instance_id": str(stage_instance_id),
                    "acted_by": str(acted_by),
                    "decision": decision,
                    "idempotency_key": idempotency_key,
                },
                values={
                    "stage_instance_id": stage_instance_id,
                    "acted_by": acted_by,
                    "decision": decision,
                    "decision_reason": decision_reason,
                    "acted_at": datetime.now(UTC),
                    "delegated_from": delegated_from,
                    "idempotency_key": idempotency_key,
                    "request_fingerprint": request_fingerprint,
                    "correlation_id": correlation_id,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=actor_user_id,
                    action="platform.workflow.approval.recorded",
                    resource_type="cp_workflow_approval",
                    new_value={"stage_instance_id": str(stage_instance_id), "decision": decision},
                ),
            )
    except IntegrityError:
        existing_result = await session.execute(
            select(CpWorkflowApproval).where(
                CpWorkflowApproval.tenant_id == tenant_id,
                CpWorkflowApproval.stage_instance_id == stage_instance_id,
                CpWorkflowApproval.acted_by == acted_by,
                CpWorkflowApproval.idempotency_key == idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is None:
            raise
        approval = existing

    approvals_result = await session.execute(
        select(CpWorkflowApproval).where(
            CpWorkflowApproval.tenant_id == tenant_id,
            CpWorkflowApproval.stage_instance_id == stage_instance_id,
        )
    )
    approvals = list(approvals_result.scalars().all())

    approve_count = sum(1 for item in approvals if item.decision == "approve")
    reject_count = sum(1 for item in approvals if item.decision == "reject")
    distinct_actor_count = len({item.acted_by for item in approvals})
    expected_count = await _expected_actor_count(
        session,
        tenant_id=tenant_id,
        stage_config=stage_config,
    )
    required_approval_count = (
        int(stage_config.threshold_value)
        if stage_config.threshold_type == "all" and stage_config.threshold_value is not None
        else expected_count
    )
    outcome = _evaluate_threshold(
        threshold_type=stage_config.threshold_type,
        threshold_value=stage_config.threshold_value,
        approve_count=approve_count,
        reject_count=reject_count,
        distinct_actor_count=distinct_actor_count,
        required_approval_count=required_approval_count,
    )

    if outcome == "approved":
        await append_stage_event(
            session,
            tenant_id=tenant_id,
            stage_instance_id=stage_instance_id,
            event_type="stage_approved",
            idempotency_key=f"stage-approved:{stage_instance_id}",
            metadata_json={"approve_count": approve_count, "reject_count": reject_count},
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
        )
        next_stage = await _get_next_stage_instance(
            session,
            tenant_id=tenant_id,
            workflow_instance_id=stage_instance.workflow_instance_id,
            current_stage_order=stage_instance.stage_order,
        )
        if next_stage is None:
            await append_workflow_event(
                session,
                tenant_id=tenant_id,
                workflow_instance_id=stage_instance.workflow_instance_id,
                event_type="instance_approved",
                idempotency_key=f"instance-approved:{stage_instance.workflow_instance_id}",
                metadata_json={"final_stage": stage_instance.stage_code},
                actor_user_id=actor_user_id,
                correlation_id=correlation_id,
            )
        else:
            await append_stage_event(
                session,
                tenant_id=tenant_id,
                stage_instance_id=next_stage.id,
                event_type="stage_running",
                idempotency_key=f"stage-running:{next_stage.id}",
                metadata_json={"triggered_by": str(stage_instance_id)},
                actor_user_id=actor_user_id,
                correlation_id=correlation_id,
            )

    if outcome == "rejected":
        await append_stage_event(
            session,
            tenant_id=tenant_id,
            stage_instance_id=stage_instance_id,
            event_type="stage_rejected",
            idempotency_key=f"stage-rejected:{stage_instance_id}",
            metadata_json={"approve_count": approve_count, "reject_count": reject_count},
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
        )
        await append_workflow_event(
            session,
            tenant_id=tenant_id,
            workflow_instance_id=stage_instance.workflow_instance_id,
            event_type="instance_rejected",
            idempotency_key=f"instance-rejected:{stage_instance.workflow_instance_id}",
            metadata_json={"rejected_stage": stage_instance.stage_code},
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
        )

    return {
        "approval_id": str(approval.id),
        "stage_instance_id": str(stage_instance_id),
        "decision": approval.decision,
        "outcome": outcome or "pending",
        "approve_count": approve_count,
        "reject_count": reject_count,
    }
