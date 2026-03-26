from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

Worker = pytest.importorskip("temporalio.worker").Worker
WorkflowEnvironment = pytest.importorskip("temporalio.testing").WorkflowEnvironment
RuntimeProbeWorkflow = pytest.importorskip(
    "financeops.temporal.workflows"
).RuntimeProbeWorkflow


@pytest.mark.asyncio
@pytest.mark.integration
async def test_temporal_runtime_probe_workflow_is_served():
    task_queue = f"financeops-runtime-probe-{uuid.uuid4()}"
    workflow_id = f"financeops-runtime-probe-{uuid.uuid4()}"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[RuntimeProbeWorkflow],
        ):
            result = await env.client.execute_workflow(
                RuntimeProbeWorkflow.run,
                "live",
                id=workflow_id,
                task_queue=task_queue,
                run_timeout=timedelta(seconds=20),
            )

    assert result == "pong:live"
