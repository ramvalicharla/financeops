from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class AIPipelineWorkflowInput:
    tenant_id: str
    task_type: str
    payload: dict


@workflow.defn
class AIPipelineWorkflow:
    @workflow.run
    async def run(self, input: AIPipelineWorkflowInput) -> dict:
        retry = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=20),
        )
        prepared = await workflow.execute_activity(
            "ai_pipeline_prepare_prompt",
            args=[input.task_type, input.payload],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )
        generated = await workflow.execute_activity(
            "ai_pipeline_generate",
            args=[input.tenant_id, prepared],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry,
        )
        return {"status": "completed", **generated}

