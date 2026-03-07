from __future__ import annotations

import pytest

RuntimeProbeWorkflow = pytest.importorskip(
    "financeops.temporal.workflows"
).RuntimeProbeWorkflow
temporal_testing = pytest.importorskip("temporalio.testing")
temporal_worker = pytest.importorskip("temporalio.worker")

WorkflowEnvironment = temporal_testing.WorkflowEnvironment
Worker = temporal_worker.Worker


@pytest.mark.asyncio
async def test_temporal_runtime_probe_workflow_runs():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "financeops-runtime-probe-test"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[RuntimeProbeWorkflow],
        ):
            result = await env.client.execute_workflow(
                RuntimeProbeWorkflow.run,
                "ok",
                id="runtime-probe-workflow-test",
                task_queue=task_queue,
            )
            assert result == "pong:ok"
