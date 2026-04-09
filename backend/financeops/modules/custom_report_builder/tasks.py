from __future__ import annotations

import asyncio
import uuid
from typing import Any

import sentry_sdk
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.modules.custom_report_builder.infrastructure.repository import ReportRepository
from financeops.modules.custom_report_builder.application.run_service import (
    InvalidReportRunStateError,
    ReportRunError,
    ReportRunService,
)
from financeops.tasks.celery_app import celery_app


@celery_app.task(
    name="custom_report_builder.run",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def run_custom_report_task(
    self,
    run_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        parsed_run_id = uuid.UUID(str(run_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = ReportRunService()
        repository = ReportRepository()
        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                run_row = None
                if hasattr(session, "execute"):
                    run_row = await repository.get_run(
                        db=session,
                        tenant_id=parsed_tenant_id,
                        run_id=parsed_run_id,
                    )
                    if run_row is None:
                        raise ReportRunError("Report run not found")
                metadata = dict(run_row.run_metadata or {}) if run_row is not None else {}
                intent_id = metadata.get("intent_id")
                job_id = metadata.get("job_id")
                if intent_id and job_id and run_row is not None:
                    with governed_mutation_context(
                        MutationContext(
                            intent_id=uuid.UUID(str(intent_id)),
                            job_id=uuid.UUID(str(job_id)),
                            actor_user_id=run_row.triggered_by,
                            actor_role=None,
                            intent_type="GENERATE_REPORT",
                        )
                    ):
                        result = await service.run(
                            db=session,
                            run_id=parsed_run_id,
                            tenant_id=parsed_tenant_id,
                        )
                else:
                    result = await service.run(
                        db=session,
                        run_id=parsed_run_id,
                        tenant_id=parsed_tenant_id,
                    )
                return {"run_id": str(parsed_run_id), "status": str(result.get("status", "COMPLETE"))}
            finally:
                await clear_tenant_context(session)

    try:
        return asyncio.run(_run())
    except (InvalidReportRunStateError, ReportRunError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


__all__ = ["run_custom_report_task"]
