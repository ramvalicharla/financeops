from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.workflow_instances import CpWorkflowStageInstance
from financeops.platform.services.workflows.approval_service import submit_approval
from financeops.platform.services.workflows.instance_service import create_workflow_instance
from financeops.platform.services.workflows.template_service import (
    create_template,
    create_template_version,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def _seed(async_session: AsyncSession, *, tenant_id, actor_user_id) -> CpModuleRegistry:
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
            "correlation_id": "corr-int-approval",
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
        module_code=f"approval-{uuid.uuid4().hex[:8]}",
        module_name="Approval Module",
        engine_context="platform",
        is_financial_impacting=False,
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
@pytest.mark.integration
async def test_parallel_approval_idempotent_under_race(async_session: AsyncSession, test_user) -> None:
    module = await _seed(async_session, tenant_id=test_user.tenant_id, actor_user_id=test_user.id)
    template = await create_template(
        async_session,
        tenant_id=test_user.tenant_id,
        template_code=f"TPL-{uuid.uuid4().hex[:6]}",
        module_id=module.id,
        actor_user_id=test_user.id,
        correlation_id="corr-int-approval",
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
                "stage_code": "approve",
                "stage_type": "approval",
                "approval_mode": "parallel",
                "threshold_type": "any",
                "threshold_value": None,
                "is_terminal": True,
                "role_ids": [],
                "user_ids": [str(test_user.id)],
            }
        ],
        actor_user_id=test_user.id,
        correlation_id="corr-int-approval",
    )
    instance = await create_workflow_instance(
        async_session,
        tenant_id=test_user.tenant_id,
        template_id=template.id,
        template_version_id=version.id,
        module_id=module.id,
        resource_type="platform_action",
        resource_id=uuid.uuid4(),
        initiated_by=test_user.id,
        correlation_id="corr-int-approval",
    )
    stage_instance_id = (
        await async_session.execute(
            select(CpWorkflowStageInstance.id).where(
                CpWorkflowStageInstance.tenant_id == test_user.tenant_id,
                CpWorkflowStageInstance.workflow_instance_id == instance.id,
            )
        )
    ).scalar_one()

    async def _approve() -> dict:
        return await submit_approval(
            async_session,
            tenant_id=test_user.tenant_id,
            stage_instance_id=stage_instance_id,
            acted_by=test_user.id,
            decision="approve",
            decision_reason=None,
            delegated_from=None,
            idempotency_key="idem-race",
            request_fingerprint="fp-race",
            actor_user_id=test_user.id,
            correlation_id="corr-int-approval",
        )

    # AsyncSession is not concurrency-safe; execute deterministically to validate idempotency.
    res1 = await _approve()
    res2 = await _approve()
    assert res1["approval_id"] == res2["approval_id"]
