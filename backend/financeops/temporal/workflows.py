from __future__ import annotations

from temporalio import workflow


@workflow.defn
class RuntimeProbeWorkflow:
    """Minimal workflow used to verify Temporal runtime wiring."""

    @workflow.run
    async def run(self, probe_value: str) -> str:
        return f"pong:{probe_value}"
