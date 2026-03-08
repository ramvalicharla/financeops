from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

WorkflowEnvironment = pytest.importorskip("temporalio.testing").WorkflowEnvironment
Worker = pytest.importorskip("temporalio.worker").Worker

from financeops.db import session as db_session  # noqa: E402
from financeops.platform.temporal.tenant_migration_activities import (  # noqa: E402
    tenant_migration_finalize_activity,
    tenant_migration_mark_running_activity,
)
from financeops.platform.temporal.tenant_migration_workflows import (  # noqa: E402
    TenantMigrationWorkflow,
    TenantMigrationWorkflowInput,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_migration_workflow_deterministic_state(engine, monkeypatch) -> None:
    test_session_local = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    monkeypatch.setattr(db_session, "AsyncSessionLocal", test_session_local)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "platform-tenant-migration-test"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[TenantMigrationWorkflow],
            activities=[
                tenant_migration_mark_running_activity,
                tenant_migration_finalize_activity,
            ],
        ):
            result = await env.client.execute_workflow(
                TenantMigrationWorkflow.run,
                TenantMigrationWorkflowInput(
                    tenant_id="00000000-0000-0000-0000-000000000001",
                    route_version=1,
                    correlation_id="corr-tenant-migration",
                    requested_by="00000000-0000-0000-0000-000000000001",
                    config_hash="cfg-1",
                ),
                id="tenant-migration-workflow-test",
                task_queue=task_queue,
            )
    assert result["status"] == "completed"
