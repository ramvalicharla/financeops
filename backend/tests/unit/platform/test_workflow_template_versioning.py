from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.workflow_stage_user_map import CpWorkflowStageUserMap
from financeops.platform.db.models.workflow_templates import CpWorkflowStageRoleMap
from financeops.platform.services.workflows.template_service import (
    create_template,
    create_template_version,
)
from financeops.platform.services.rbac.role_service import create_role
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def _seed_tenant_and_module(async_session: AsyncSession, *, tenant_id, actor_user_id):
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CpTenant,
        tenant_id=tenant_id,
        record_data={"tenant_code": f"TEN-{str(tenant_id)[:8]}", "status": "active"},
        values={
            "id": tenant_id,
            "tenant_code": f"TEN-{str(tenant_id)[:8]}",
            "display_name": "Tenant",
            "country_code": "US",
            "region": "us-east-1",
            "billing_tier": "pro",
            "status": "active",
            "correlation_id": "corr-workflow",
            "deactivated_at": None,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.test.seed",
            resource_type="cp_tenant",
            resource_id=str(tenant_id),
        ),
    )
    module = CpModuleRegistry(
        module_code=f"mod-{str(tenant_id)[:8]}",
        module_name="Module",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    await AuditWriter.insert_record(
        async_session,
        record=module,
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.test.module.seed",
            resource_type="cp_module_registry",
            resource_id=str(module.id),
        ),
    )
    return module


@pytest.mark.asyncio
async def test_workflow_template_version_rejects_duplicate_stage_order(
    async_session: AsyncSession,
    test_user,
) -> None:
    module = await _seed_tenant_and_module(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )
    template = await create_template(
        async_session,
        tenant_id=test_user.tenant_id,
        template_code="REV_APPROVAL",
        module_id=module.id,
        actor_user_id=test_user.id,
        correlation_id="corr-workflow",
    )
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        await create_template_version(
            async_session,
            tenant_id=test_user.tenant_id,
            template_id=template.id,
            version_no=1,
            effective_from=now,
            effective_to=None,
            stages=[
                {
                    "stage_order": 1,
                    "stage_code": "review",
                    "stage_type": "review",
                    "approval_mode": "parallel",
                    "threshold_type": "any",
                    "is_terminal": False,
                    "role_ids": [],
                    "user_ids": [str(test_user.id)],
                },
                {
                    "stage_order": 1,
                    "stage_code": "approve",
                    "stage_type": "approval",
                    "approval_mode": "parallel",
                    "threshold_type": "all",
                    "is_terminal": True,
                    "role_ids": [],
                    "user_ids": [str(test_user.id)],
                },
            ],
            actor_user_id=test_user.id,
            correlation_id="corr-workflow",
        )


@pytest.mark.asyncio
async def test_workflow_template_supports_role_and_named_user_assignment(
    async_session: AsyncSession,
    test_user,
) -> None:
    module = await _seed_tenant_and_module(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )
    role = await create_role(
        async_session,
        tenant_id=test_user.tenant_id,
        role_code="WF_REVIEWER",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=test_user.id,
        correlation_id="corr-workflow",
    )
    template = await create_template(
        async_session,
        tenant_id=test_user.tenant_id,
        template_code="MIXED_ASSIGNMENT",
        module_id=module.id,
        actor_user_id=test_user.id,
        correlation_id="corr-workflow",
    )
    version = await create_template_version(
        async_session,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        version_no=1,
        effective_from=datetime.now(UTC),
        effective_to=None,
        stages=[
            {
                "stage_order": 1,
                "stage_code": "review",
                "stage_type": "review",
                "approval_mode": "parallel",
                "threshold_type": "any",
                "threshold_value": None,
                "is_terminal": False,
                "role_ids": [str(role.id)],
                "user_ids": [str(test_user.id)],
            }
        ],
        actor_user_id=test_user.id,
        correlation_id="corr-workflow",
    )
    role_map_count = (
        await async_session.execute(
            select(CpWorkflowStageRoleMap.id).where(
                CpWorkflowStageRoleMap.tenant_id == test_user.tenant_id,
            )
        )
    ).scalars().all()
    user_map_count = (
        await async_session.execute(
            select(CpWorkflowStageUserMap.id).where(
                CpWorkflowStageUserMap.tenant_id == test_user.tenant_id,
            )
        )
    ).scalars().all()
    assert version.version_no == 1
    assert len(role_map_count) >= 1
    assert len(user_map_count) >= 1
