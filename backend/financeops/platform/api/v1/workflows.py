from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    require_finance_team,
    require_user_plane_permission,
)
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.schemas.workflows import (
    WorkflowApprovalRequest,
    WorkflowInstanceCreate,
    WorkflowTemplateCreate,
    WorkflowTemplateVersionCreate,
)
from financeops.platform.services.rbac.permission_engine import require_permission
from financeops.platform.services.workflows.approval_service import submit_approval
from financeops.platform.services.workflows.instance_service import create_workflow_instance, get_workflow_status
from financeops.platform.services.workflows.template_service import create_template, create_template_version

router = APIRouter()

workflow_manage_guard = require_user_plane_permission(
    resource_type="workflow",
    action="manage",
    fallback_roles={
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.finance_leader,
    },
    fallback_error_message="finance_approver role required",
)
workflow_approve_guard = require_user_plane_permission(
    resource_type="workflow_approval",
    action="approve",
    fallback_roles={
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.finance_leader,
    },
    fallback_error_message="finance_approver role required",
)
workflow_approve_matrix_guard = require_permission("workflow.approve")
workflow_manage_matrix_guard = require_permission("workflow.view")


@router.post("/templates")
async def create_template_endpoint(
    body: WorkflowTemplateCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(workflow_manage_guard),
    _: IamUser = Depends(workflow_manage_matrix_guard),
) -> dict:
    template = await create_template(
        session,
        tenant_id=user.tenant_id,
        template_code=body.template_code,
        module_id=body.module_id,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(template.id), "template_code": template.template_code}


@router.post("/template-versions")
async def create_template_version_endpoint(
    body: WorkflowTemplateVersionCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(workflow_manage_guard),
    _: IamUser = Depends(workflow_manage_matrix_guard),
) -> dict:
    version = await create_template_version(
        session,
        tenant_id=user.tenant_id,
        template_id=body.template_id,
        version_no=body.version_no,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        stages=[stage.model_dump() for stage in body.stages],
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(version.id), "version_no": version.version_no}


@router.post("/instances")
async def create_instance_endpoint(
    body: WorkflowInstanceCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(workflow_manage_guard),
    _: IamUser = Depends(workflow_manage_matrix_guard),
) -> dict:
    instance = await create_workflow_instance(
        session,
        tenant_id=user.tenant_id,
        template_id=body.template_id,
        template_version_id=body.template_version_id,
        module_id=body.module_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        initiated_by=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(instance.id)}


@router.post("/approvals")
async def submit_approval_endpoint(
    body: WorkflowApprovalRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(workflow_approve_guard),
    _: IamUser = Depends(workflow_approve_matrix_guard),
) -> dict:
    result = await submit_approval(
        session,
        tenant_id=user.tenant_id,
        stage_instance_id=body.stage_instance_id,
        acted_by=body.acted_by,
        decision=body.decision,
        decision_reason=body.decision_reason,
        delegated_from=body.delegated_from,
        idempotency_key=body.idempotency_key,
        request_fingerprint=body.request_fingerprint,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return result


@router.get("/instances/{workflow_instance_id}/status")
async def get_workflow_status_endpoint(
    workflow_instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
    _: IamUser = Depends(workflow_manage_matrix_guard),
) -> dict:
    return await get_workflow_status(
        session,
        tenant_id=user.tenant_id,
        workflow_instance_id=workflow_instance_id,
    )
