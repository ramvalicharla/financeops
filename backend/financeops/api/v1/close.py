from __future__ import annotations

from datetime import timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from temporalio.exceptions import WorkflowAlreadyStartedError

from financeops.api.deps import require_finance_leader
from financeops.config import settings
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.db.models.users import IamUser
from financeops.workflows.month_end_close.workflow import (
    MonthEndCloseInput,
    MonthEndCloseWorkflow,
)

router = APIRouter(prefix="/close", tags=["month-end-close"])


class CloseTriggerRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_month_end_close(
    body: CloseTriggerRequest,
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    dispatcher = JobDispatcher()
    workflow_id = f"month-end-close-{user.tenant_id}-{body.period}"
    payload = MonthEndCloseInput(
        tenant_id=str(user.tenant_id),
        period=body.period,
    )
    try:
        handle = await dispatcher.start_temporal_workflow(
            MonthEndCloseWorkflow.run,
            payload,
            workflow_id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=90),
        )
    except WorkflowAlreadyStartedError:
        handle = await dispatcher.get_temporal_workflow_handle(workflow_id)

    return {
        "workflow_id": handle.id,
        "status": "started",
        "period": body.period,
    }


@router.get("/{workflow_id}/status")
async def get_month_end_close_status(
    workflow_id: str,
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    _ = user
    handle = await JobDispatcher().get_temporal_workflow_handle(workflow_id)
    try:
        description = await handle.describe()
    except Exception as exc:
        raise HTTPException(status_code=404, detail="workflow_not_found") from exc

    status_name = str(getattr(description.status, "name", "RUNNING")).lower()
    if status_name in {"completed"}:
        mapped = "completed"
    elif status_name in {"failed", "terminated", "timed_out"}:
        mapped = "failed"
    else:
        mapped = "running"

    result_payload = None
    if mapped == "completed":
        try:
            result_payload = await handle.result()
            if isinstance(result_payload, dict) and result_payload.get("status") == "partial":
                mapped = "partial"
        except Exception:
            result_payload = None

    return {
        "workflow_id": workflow_id,
        "status": mapped,
        "result": result_payload,
    }
