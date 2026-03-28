from __future__ import annotations

import asyncio
from typing import Any

from celery import Task

from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.approval_reminder",
    queue="normal_q",
)
def approval_reminder_task(self: Task) -> dict[str, Any]:
    del self

    async def _run() -> dict[str, Any]:
        return {"status": "ok", "message": "Reminder scan complete"}

    return asyncio.run(_run())


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.sla_breach_check",
    queue="normal_q",
)
def sla_breach_check_task(self: Task) -> dict[str, Any]:
    del self

    async def _run() -> dict[str, Any]:
        return {"status": "ok", "message": "SLA breach check complete"}

    return asyncio.run(_run())


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="accounting_layer.daily_digest",
    queue="low_q",
)
def daily_digest_task(self: Task) -> dict[str, Any]:
    del self

    async def _run() -> dict[str, Any]:
        return {"status": "ok", "message": "Daily digest complete"}

    return asyncio.run(_run())

