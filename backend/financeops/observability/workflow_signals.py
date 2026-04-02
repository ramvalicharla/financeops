from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from financeops.observability.business_metrics import (
    close_readiness_failures_counter,
    erp_sync_counter,
    erp_sync_duration_ms,
    finance_workflow_counter,
    finance_workflow_duration_ms,
    governance_operation_counter,
)

log = logging.getLogger(__name__)


@dataclass
class WorkflowTimer:
    workflow: str
    started_at: float
    tenant_id: str
    correlation_id: str | None
    run_id: str | None
    module: str


def start_workflow(
    *,
    workflow: str,
    tenant_id: str,
    module: str,
    correlation_id: str | None = None,
    run_id: str | None = None,
) -> WorkflowTimer:
    finance_workflow_counter.labels(workflow=workflow, status="started").inc()
    log.info(
        "workflow_started",
        extra={
            "event": "workflow_started",
            "module_name": module,
            "workflow": workflow,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "run_id": run_id,
        },
    )
    return WorkflowTimer(
        workflow=workflow,
        started_at=time.perf_counter(),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        run_id=run_id,
        module=module,
    )


def complete_workflow(timer: WorkflowTimer, *, status: str = "success", extra: dict[str, Any] | None = None) -> None:
    duration_ms = (time.perf_counter() - timer.started_at) * 1000
    finance_workflow_counter.labels(workflow=timer.workflow, status=status).inc()
    finance_workflow_duration_ms.labels(workflow=timer.workflow, status=status).observe(duration_ms)
    payload = {
        "event": "workflow_completed",
        "module_name": timer.module,
        "workflow": timer.workflow,
        "tenant_id": timer.tenant_id,
        "correlation_id": timer.correlation_id,
        "run_id": timer.run_id,
        "status": status,
        "duration_ms": round(duration_ms, 2),
    }
    if extra:
        payload.update(extra)
    log.info("workflow_completed", extra=payload)


def fail_workflow(timer: WorkflowTimer, *, error: Exception) -> None:
    duration_ms = (time.perf_counter() - timer.started_at) * 1000
    finance_workflow_counter.labels(workflow=timer.workflow, status="failed").inc()
    finance_workflow_duration_ms.labels(workflow=timer.workflow, status="failed").observe(duration_ms)
    log.error(
        "workflow_failed",
        extra={
            "event": "workflow_failed",
            "module_name": timer.module,
            "workflow": timer.workflow,
            "tenant_id": timer.tenant_id,
            "correlation_id": timer.correlation_id,
            "run_id": timer.run_id,
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "duration_ms": round(duration_ms, 2),
        },
    )


def observe_erp_sync(*, operation: str, status: str, connector_type: str, duration_ms: float | None = None) -> None:
    erp_sync_counter.labels(connector_type=connector_type, status=status).inc()
    if duration_ms is not None:
        erp_sync_duration_ms.labels(operation=operation, status=status).observe(duration_ms)


def observe_governance_operation(*, operation: str, status: str) -> None:
    governance_operation_counter.labels(operation=operation, status=status).inc()


def observe_close_readiness_failure(*, reason: str) -> None:
    close_readiness_failures_counter.labels(reason=reason).inc()
