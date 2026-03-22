from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from financeops.config import get_settings
from financeops.workflows.ai_pipeline.activities import (
    ai_pipeline_generate,
    ai_pipeline_prepare_prompt,
)
from financeops.workflows.ai_pipeline.workflow import AIPipelineWorkflow
from financeops.workflows.month_end_close.activities import (
    generate_board_pack,
    notify_completion,
    recompute_mis,
    run_anomaly_detection,
    run_consolidation,
    run_gl_reconciliation,
    sync_erp_data,
)
from financeops.workflows.month_end_close.workflow import MonthEndCloseWorkflow

log = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE,
    )
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[MonthEndCloseWorkflow, AIPipelineWorkflow],
        activities=[
            sync_erp_data,
            run_gl_reconciliation,
            run_consolidation,
            recompute_mis,
            run_anomaly_detection,
            generate_board_pack,
            notify_completion,
            ai_pipeline_prepare_prompt,
            ai_pipeline_generate,
        ],
    )
    log.info(
        "Temporal worker starting on queue=%s namespace=%s",
        settings.TEMPORAL_TASK_QUEUE,
        settings.TEMPORAL_NAMESPACE,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())

