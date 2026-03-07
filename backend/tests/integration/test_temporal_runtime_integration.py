from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

Worker = pytest.importorskip("temporalio.worker").Worker
get_temporal_client = pytest.importorskip(
    "financeops.temporal.client"
).get_temporal_client
RuntimeProbeWorkflow = pytest.importorskip(
    "financeops.temporal.workflows"
).RuntimeProbeWorkflow


@pytest.mark.asyncio
@pytest.mark.integration
async def test_temporal_runtime_probe_workflow_is_served():
    try:
        client = await get_temporal_client()
    except Exception as exc:
        pytest.skip(f"Temporal service unavailable: {exc}")

    task_queue = f"financeops-runtime-probe-{uuid.uuid4()}"
    workflow_id = f"financeops-runtime-probe-{uuid.uuid4()}"
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[RuntimeProbeWorkflow],
    ):
        result = await client.execute_workflow(
            RuntimeProbeWorkflow.run,
            "live",
            id=workflow_id,
            task_queue=task_queue,
            run_timeout=timedelta(seconds=20),
        )

    assert result == "pong:live"
